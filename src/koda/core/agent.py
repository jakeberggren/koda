import asyncio
from collections.abc import AsyncIterator

from langfuse import observe

from koda import providers
from koda.core import message
from koda.providers import TextDelta, ToolCallRequested
from koda.tools import ToolDefinition
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

    @observe(name="agent.stream", as_type="agent")
    async def run(self, user_text: str) -> AsyncIterator[TextDelta | ToolCallRequested]:
        if not user_text or not user_text.strip():
            raise exceptions.ProviderValidationError("Message cannot be empty")

        user_message = message.UserMessage(content=user_text.strip())
        self._history.append(user_message)

        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1

            messages = self._build_messages()
            tools = self._build_tool_definitions()
            stream = self.provider.stream(messages, tools)

            response_chunks: list[str] = []
            pending_tool_calls: list[ToolCall] = []

            async for chunk in stream:
                if isinstance(chunk, TextDelta):
                    response_chunks.append(chunk.text)
                    yield chunk
                elif isinstance(chunk, ToolCallRequested):
                    pending_tool_calls.append(chunk.call)

            if pending_tool_calls:
                tool_results = await self._execute_tools(pending_tool_calls)

                tool_call_msg = message.ToolCallMessage(tool_calls=pending_tool_calls)
                self._history.append(tool_call_msg)

                # Add tool result messages to history
                for tool_call, tool_result in zip(pending_tool_calls, tool_results, strict=True):
                    tool_result_msg = message.ToolResultMessage(
                        tool_name=tool_call.tool_name,
                        result=tool_result,
                        call_id=tool_call.call_id,
                    )
                    self._history.append(tool_result_msg)

                continue

            response_text = "".join(response_chunks)
            if response_text:
                assistant_message = message.AssistantMessage(content=response_text)
                self._history.append(assistant_message)
            return

        # Max iterations exceeded
        raise exceptions.MaxIterationsExceededError(
            f"Maximum tool call iterations ({self.max_tool_iterations}) exceeded"
        )

    def add_message(self, message_to_add: message.Message) -> None:
        self._history.append(message_to_add)

    def get_history(self) -> list[message.Message]:
        return self._history.copy()

    def clear_history(self) -> None:
        # Preserve system message if it exists
        system_msg = None
        if self._history and self._history[0].role.value == "system":
            system_msg = self._history[0]

        self._history.clear()

        # Restore system message if it existed
        if system_msg:
            self._history.append(system_msg)

    def reset(self) -> None:
        self.clear_history()

        # Reset provider state if it has a reset_state method
        reset_state = getattr(self.provider, "reset_state", None)
        if reset_state is not None and callable(reset_state):
            reset_state()

    def _build_messages(self) -> list[message.Message]:
        return self._history.copy()

    def _build_tool_definitions(self) -> list[ToolDefinition]:
        """Get tool definitions from registry."""
        if not self.tool_registry:
            return []
        return self.tool_registry.get_definitions()

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tools in parallel."""
        if not self.tool_registry:
            raise exceptions.ToolError("No tool registry available")

        async def execute_single_tool(tool_call: ToolCall) -> ToolResult:
            """Execute a single tool call."""
            try:
                # Get tool from registry
                if not self.tool_registry:
                    return ToolResult(
                        content=None,
                        is_error=True,
                        error_message="No tool registry available",
                        call_id=tool_call.call_id,
                    )

                tool = self.tool_registry.get(tool_call.tool_name)
                if not tool:
                    return ToolResult(
                        content=None,
                        is_error=True,
                        error_message=f"Tool '{tool_call.tool_name}' not found",
                        call_id=tool_call.call_id,
                    )

                # Validate arguments against tool's Pydantic model
                try:
                    validated_params = tool.parameters_model.model_validate(tool_call.arguments)
                except Exception as e:
                    return ToolResult(
                        content=None,
                        is_error=True,
                        error_message=f"Validation error: {e}",
                        call_id=tool_call.call_id,
                    )

                # Execute tool
                try:
                    result = await tool.execute(validated_params)
                    result.call_id = tool_call.call_id
                    return result
                except Exception as e:
                    return ToolResult(
                        content=None,
                        is_error=True,
                        error_message=f"Execution error: {e}",
                        call_id=tool_call.call_id,
                    )

            except Exception as e:
                return ToolResult(
                    content=None,
                    is_error=True,
                    error_message=f"Unexpected error: {e}",
                    call_id=tool_call.call_id,
                )

        # Execute all tools in parallel
        results = await asyncio.gather(*[execute_single_tool(call) for call in tool_calls])
        return list(results)
