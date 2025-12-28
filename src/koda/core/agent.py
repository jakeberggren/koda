import asyncio
from collections.abc import AsyncIterator

from langfuse import observe

from koda import providers
from koda.core import message
from koda.providers import ProviderEvent, TextDelta, ToolCallRequested
from koda.tools.base import ToolCall, ToolResult
from koda.tools.registry import ToolRegistry
from koda.utils import exceptions


class Agent:
    def __init__(
        self,
        provider: providers.Provider,
        system_message: str | None = None,
        tool_registry: ToolRegistry | None = None,
        max_tool_iterations: int = 30,
    ) -> None:
        self.provider: providers.Provider = provider
        self.system_message: str | None = system_message
        self.tool_registry: ToolRegistry | None = tool_registry
        self.max_tool_iterations: int = max_tool_iterations
        self._history: list[message.Message] = []

        if system_message:
            self._history.append(message.SystemMessage(content=system_message))

    @observe(name="agent.run", as_type="agent")
    async def run(self, user_text: str) -> AsyncIterator[ProviderEvent]:
        if not user_text or not user_text.strip():
            raise exceptions.ProviderValidationError("Message cannot be empty")

        user_message = message.UserMessage(content=user_text.strip())
        self._history.append(user_message)
        tools = self.tool_registry.get_definitions() if self.tool_registry else None

        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            messages = self._history.copy()
            stream = self.provider.stream(messages, tools)

            response_chunks: list[str] = []
            pending_tool_calls: list[ToolCall] = []
            async for event in stream:
                if isinstance(event, TextDelta):
                    response_chunks.append(event.text)
                    yield event
                elif isinstance(event, ToolCallRequested):
                    pending_tool_calls.append(event.call)
                    yield event

            result_text = "".join(response_chunks)
            assistant_message = message.AssistantMessage(
                content=result_text,
                tool_calls=pending_tool_calls,
            )

            self._history.append(assistant_message)

            if pending_tool_calls:
                tool_results = await self._execute_tools(pending_tool_calls)
                for tool_call, tool_result in zip(pending_tool_calls, tool_results, strict=True):
                    self._history.append(
                        message.ToolMessage(
                            tool_name=tool_call.tool_name,
                            result=tool_result,
                            call_id=tool_call.call_id,
                        )
                    )
                continue

            return

        raise exceptions.MaxIterationsExceededError(
            f"Maximum tool call iterations ({self.max_tool_iterations}) exceeded"
        )

    def add_message(self, message_to_add: message.Message) -> None:
        self._history.append(message_to_add)

    def get_history(self) -> list[message.Message]:
        return self._history.copy()

    def clear_history(self) -> None:
        system_msg = None
        if self._history and self._history[0].role.value == "system":
            system_msg = self._history[0]

        self._history.clear()

        if system_msg:
            self._history.append(system_msg)

    def reset(self) -> None:
        self.clear_history()

        reset_state = getattr(self.provider, "reset_state", None)
        if reset_state is not None and callable(reset_state):
            reset_state()

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tools in parallel."""

        if self.tool_registry is None:
            return [
                ToolResult(
                    content=None,
                    is_error=True,
                    error_message="No tool registry configured",
                    call_id=call.call_id,
                )
                for call in tool_calls
            ]

        registry = self.tool_registry

        async def execute_single_tool(tool_call: ToolCall) -> ToolResult:
            tool = registry.get(tool_call.tool_name)
            if not tool:
                return ToolResult(
                    content=None,
                    is_error=True,
                    error_message=f"Tool '{tool_call.tool_name}' not found",
                    call_id=tool_call.call_id,
                )

            try:
                params = tool.parameters_model.model_validate(tool_call.arguments)
            except Exception as e:
                return ToolResult(
                    content=None,
                    is_error=True,
                    error_message=f"Validation error: {e}",
                    call_id=tool_call.call_id,
                )

            try:
                result = await tool.execute(params)
                result.call_id = tool_call.call_id
                return result
            except Exception as e:
                return ToolResult(
                    content=None,
                    is_error=True,
                    error_message=f"Execution error: {e}",
                    call_id=tool_call.call_id,
                )

        results = await asyncio.gather(*[execute_single_tool(call) for call in tool_calls])
        return list(results)
