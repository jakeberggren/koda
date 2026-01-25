from __future__ import annotations

from typing import TYPE_CHECKING

from koda.messages import AssistantMessage, Message, SystemMessage, ToolMessage, UserMessage
from koda.providers import exceptions as provider_exceptions
from koda.providers.events import ProviderEvent, TextDelta, ToolCallRequested, ToolCallResult
from koda.tools import ToolCall, ToolDefinition, ToolOutput, ToolResult
from koda.tools import exceptions as tool_exceptions
from koda.tools.executor import ToolExecutor
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.providers import Provider
    from koda.tools.config import ToolConfig

logger = get_logger(__name__)


class Agent:
    def __init__(
        self,
        provider: Provider,
        system_message: str | None = None,
        tools: ToolConfig | None = None,
        max_tool_iterations: int = 30,
    ) -> None:
        self.provider: Provider = provider
        self.system_message: str | None = system_message
        self.tools: ToolConfig | None = tools
        self.max_tool_iterations: int = max_tool_iterations
        self._history: list[Message] = []

        if system_message:
            self._history.append(SystemMessage(content=system_message))

        logger.info("agent_initialized", provider=type(provider).__name__)

    def _validate_and_add_user_message(self, user_text: str) -> None:
        """Validate user input and add to history."""
        if not user_text or not user_text.strip():
            logger.warning("run_called_with_empty_message")
            raise provider_exceptions.EmptyMessageError
        logger.info("agent_run_started", user_text_length=len(user_text.strip()))
        self._history.append(UserMessage(content=user_text.strip()))

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

    async def _handle_tool_calls(self, tool_calls: list[ToolCall]) -> AsyncIterator[ToolCallResult]:
        if self.tools is None:
            # If provider requested tool calls but we don't have tools configured,
            # record errors for each tool call.
            logger.warning("tool_calls_requested_but_no_tools_configured", count=len(tool_calls))
            for tool_call in tool_calls:
                tool_result = ToolResult(
                    call_id=tool_call.call_id,
                    output=ToolOutput(is_error=True, error_message="No tools configured"),
                )
                self._history.append(
                    ToolMessage(
                        tool_name=tool_call.tool_name,
                        tool_result=tool_result,
                    ),
                )
                yield ToolCallResult(
                    tool_name=tool_call.tool_name,
                    result=tool_result,
                )
            return

        executor = ToolExecutor(self.tools.registry)
        tool_results = await executor.execute_calls(tool_calls, self.tools.context)

        for tool_call, tool_result in zip(tool_calls, tool_results, strict=True):
            self._history.append(
                ToolMessage(
                    tool_name=tool_call.tool_name,
                    tool_result=tool_result,
                )
            )
            yield ToolCallResult(
                tool_name=tool_call.tool_name,
                result=tool_result,
            )

    async def _run_iteration(
        self,
        tool_definitions: list[ToolDefinition] | None,
        pending_tool_calls: list[ToolCall],
    ) -> AsyncIterator[ProviderEvent]:
        """Run a single iteration, streaming events as they occur."""
        stream = self.provider.stream(self._history.copy(), tool_definitions)
        response_chunks: list[str] = []

        async for event in self._process_events(stream, response_chunks, pending_tool_calls):
            yield event

        self._history.append(
            AssistantMessage(
                content="".join(response_chunks),
                tool_calls=pending_tool_calls,
            )
        )

        if pending_tool_calls:
            logger.info("tool_calls_pending", count=len(pending_tool_calls))
            async for event in self._handle_tool_calls(tool_calls=pending_tool_calls):
                yield event

    async def run(self, user_text: str) -> AsyncIterator[ProviderEvent]:
        self._validate_and_add_user_message(user_text)
        tool_definitions = self.tools.registry.get_definitions() if self.tools else None

        for iteration in range(1, self.max_tool_iterations + 1):
            logger.info("agent_loop_iteration", iteration=iteration)
            pending_tool_calls: list[ToolCall] = []

            async for event in self._run_iteration(tool_definitions, pending_tool_calls):
                yield event

            if not pending_tool_calls:
                logger.info("run_completed", iterations=iteration)
                return

        logger.error("max_iterations_exceeded", max_iterations=self.max_tool_iterations)
        raise tool_exceptions.MaxIterationsExceededError(self.max_tool_iterations)

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
