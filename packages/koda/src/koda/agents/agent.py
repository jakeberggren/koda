from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import ValidationError

from koda.messages import AssistantMessage, Message, SystemMessage, ToolMessage, UserMessage
from koda.providers import exceptions as provider_exceptions
from koda.providers.events import ProviderEvent, TextDelta, ToolCallRequested
from koda.tools import ToolCall, ToolOutput, ToolRegistry, ToolResult
from koda.tools import exceptions as tool_exceptions

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.providers import Provider


class Agent:
    def __init__(
        self,
        provider: Provider,
        system_message: str | None = None,
        tool_registry: ToolRegistry | None = None,
        max_tool_iterations: int = 30,
    ) -> None:
        self.provider: Provider = provider
        self.system_message: str | None = system_message
        self.tool_registry: ToolRegistry | None = tool_registry
        self.max_tool_iterations: int = max_tool_iterations
        self._history: list[Message] = []

        if system_message:
            self._history.append(SystemMessage(content=system_message))

    async def run(self, user_text: str) -> AsyncIterator[ProviderEvent]:
        if not user_text or not user_text.strip():
            raise provider_exceptions.ProviderValidationError("Message cannot be empty")

        user_message = UserMessage(content=user_text.strip())
        self._history.append(user_message)
        tools = self.tool_registry.get_definitions() if self.tool_registry else None

        iteration = 0
        while iteration < self.max_tool_iterations:
            iteration += 1
            messages: list[Message] = self._history.copy()
            stream: AsyncIterator[ProviderEvent] = self.provider.stream(messages, tools)

            response_chunks: list[str] = []
            pending_tool_calls: list[ToolCall] = []
            async for event in self._process_events(stream, response_chunks, pending_tool_calls):
                yield event

            result_text = "".join(response_chunks)
            assistant_message = AssistantMessage(
                content=result_text,
                tool_calls=pending_tool_calls,
            )

            self._history.append(assistant_message)

            if pending_tool_calls:
                await self._handle_tool_calls(tool_calls=pending_tool_calls)
                continue
            return

        raise tool_exceptions.MaxIterationsExceededError(
            f"Maximum tool call iterations ({self.max_tool_iterations}) exceeded",
        )

    def add_message(self, message_to_add: Message) -> None:
        self._history.append(message_to_add)

    def get_history(self) -> list[Message]:
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

    async def _process_events(
        self,
        stream: AsyncIterator[ProviderEvent],
        response_chunks: list[str],
        pending_tool_calls: list[ToolCall],
    ) -> AsyncIterator[ProviderEvent]:
        async for event in stream:
            if isinstance(event, TextDelta):
                response_chunks.append(event.text)
                yield event
            elif isinstance(event, ToolCallRequested):
                pending_tool_calls.append(event.call)
                yield event

    async def _handle_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        tool_results = await self._execute_tools(tool_calls)
        for tool_call, tool_result in zip(tool_calls, tool_results, strict=True):
            self._history.append(
                ToolMessage(
                    tool_name=tool_call.tool_name,
                    tool_result=tool_result,
                ),
            )

    async def _execute_tools(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tools in parallel."""

        if self.tool_registry is None:
            return [
                ToolResult(
                    output=ToolOutput(is_error=True, error_message="No tool registry configured"),
                    call_id=call.call_id,
                )
                for call in tool_calls
            ]

        return await asyncio.gather(
            *[self._execute_single_tool(self.tool_registry, call) for call in tool_calls],
        )

    async def _execute_single_tool(
        self, tool_registry: ToolRegistry, tool_call: ToolCall
    ) -> ToolResult:
        tool = tool_registry.get(tool_call.tool_name)
        if not tool:
            return ToolResult(
                output=ToolOutput(
                    is_error=True,
                    error_message=f"Tool '{tool_call.tool_name}' not found",
                ),
                call_id=tool_call.call_id,
            )

        try:
            params = tool.parameters_model.model_validate(tool_call.arguments)
        except ValidationError as e:
            return ToolResult(
                output=ToolOutput(is_error=True, error_message=str(e)),
                call_id=tool_call.call_id,
            )

        try:
            output = await tool.execute(params)
            return ToolResult(output=output, call_id=tool_call.call_id)
        except Exception as e:
            return ToolResult(
                output=ToolOutput(is_error=True, error_message=f"{type(e).__name__}: {e}"),
                call_id=tool_call.call_id,
            )
