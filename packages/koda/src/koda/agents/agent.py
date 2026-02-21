from __future__ import annotations

from typing import TYPE_CHECKING

from koda.messages import AssistantMessage, ToolMessage, UserMessage
from koda.providers import exceptions as provider_exceptions
from koda.providers.events import (
    ProviderEvent,
    ProviderToolCompleted,
    ProviderToolStarted,
    TextDelta,
    ToolCallRequested,
    ToolCallResult,
)
from koda.tools import ToolCall, ToolDefinition, ToolOutput, ToolResult
from koda.tools import exceptions as tool_exceptions
from koda.tools.executor import ToolExecutor
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from koda.providers import Provider
    from koda.sessions import Session, SessionManager
    from koda.sessions.session import SessionMessage
    from koda.tools import ToolConfig

logger = get_logger(__name__)


class Agent:
    def __init__(
        self,
        provider: Provider,
        session_manager: SessionManager,
        system_message: str | None = None,
        tools: ToolConfig | None = None,
        max_tool_iterations: int = 30,
    ) -> None:
        self.provider: Provider = provider
        self._session_manager: SessionManager = session_manager
        self._system_message: str | None = system_message
        self.tools: ToolConfig | None = tools
        self.max_tool_iterations: int = max_tool_iterations

        logger.info("agent_initialized", provider=type(provider).__name__)

    def _append_message(self, session_id: UUID, message: SessionMessage) -> None:
        """Append a message to the session."""
        self._session_manager.append_message(session_id, message)

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
            elif isinstance(event, (ProviderToolStarted, ProviderToolCompleted)):
                yield event

    async def _handle_tool_calls(
        self, session_id: UUID, tool_calls: list[ToolCall]
    ) -> AsyncIterator[ToolCallResult]:
        if self.tools is None:
            # If provider requested tool calls but we don't have tools configured,
            # record errors for each tool call.
            logger.warning("tool_calls_requested_but_no_tools_configured", count=len(tool_calls))
            for tool_call in tool_calls:
                tool_result = ToolResult(
                    call_id=tool_call.call_id,
                    output=ToolOutput(is_error=True, error_message="No tools configured"),
                )
                self._append_message(
                    session_id,
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
            self._append_message(
                session_id,
                ToolMessage(
                    tool_name=tool_call.tool_name,
                    tool_result=tool_result,
                ),
            )
            yield ToolCallResult(
                tool_name=tool_call.tool_name,
                result=tool_result,
            )

    async def _run_iteration(
        self,
        session_id: UUID,
        tool_definitions: list[ToolDefinition] | None,
        pending_tool_calls: list[ToolCall],
    ) -> AsyncIterator[ProviderEvent]:
        """Run a single iteration, streaming events as they occur."""
        session = self._session_manager.get_session(session_id)
        stream = self.provider.stream(session.messages, self._system_message, tool_definitions)
        response_chunks: list[str] = []

        async for event in self._process_events(stream, response_chunks, pending_tool_calls):
            yield event

        content = "".join(response_chunks)
        if content or pending_tool_calls:
            self._append_message(
                session_id,
                AssistantMessage(
                    content=content,
                    tool_calls=pending_tool_calls,
                ),
            )

        if pending_tool_calls:
            logger.info("tool_calls_pending", count=len(pending_tool_calls))
            async for event in self._handle_tool_calls(session_id, tool_calls=pending_tool_calls):
                yield event

    async def run(self, user_text: str) -> AsyncIterator[ProviderEvent]:
        logger.info("agent_run_started")

        # validate user input
        if not user_text or not user_text.strip():
            logger.warning("run_called_with_empty_message")
            raise provider_exceptions.EmptyMessageError

        session_id = self._session_manager.active_session.session_id
        self._append_message(session_id, UserMessage(content=user_text.strip()))

        tool_definitions = self.tools.registry.get_definitions() if self.tools else None

        for iteration in range(1, self.max_tool_iterations + 1):
            logger.info("agent_loop_iteration", iteration=iteration)
            pending_tool_calls: list[ToolCall] = []

            async for event in self._run_iteration(
                session_id,
                tool_definitions,
                pending_tool_calls,
            ):
                yield event

            if not pending_tool_calls:
                logger.info("run_completed", iterations=iteration)
                return

        logger.error("max_iterations_exceeded", max_iterations=self.max_tool_iterations)
        raise tool_exceptions.MaxIterationsExceededError(self.max_tool_iterations)

    @property
    def active_session(self) -> Session:
        return self._session_manager.active_session

    def new_session(self) -> Session:
        return self._session_manager.create_session()

    def list_sessions(self) -> list[Session]:
        return self._session_manager.list_sessions()

    def switch_session(self, session_id: UUID) -> Session:
        return self._session_manager.switch_session(session_id)

    def delete_session(self, session_id: UUID) -> Session | None:
        """Delete a session. Returns the new active session if the deleted one was active."""
        return self._session_manager.delete_session(session_id)
