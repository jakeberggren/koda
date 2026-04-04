from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.agents.prompts import (
    PromptContext,
    SystemPrompt,
    render_prompt,
)
from koda.llm import LLM, LLMRequest, LLMRequestOptions
from koda.llm import exceptions as llm_exceptions
from koda.llm.types import (
    LLMEvent,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
    LLMToolCallResult,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.messages import AssistantMessage, ToolMessage, UserMessage
from koda.tools import ToolCall, ToolDefinition, ToolOutput, ToolResult
from koda.tools import exceptions as tool_exceptions
from koda.tools.executor import ToolExecutor
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from koda.sessions import Session, SessionManager
    from koda.sessions.session import SessionMessage
    from koda.tools import ToolConfig

logger = get_logger(__name__)


class AgentConfigError(Exception):
    """Raised when agent config is invalid."""

    def __init__(self, field_name: str, value: object, expected: str) -> None:
        self.field_name = field_name
        self.value = value
        self.expected = expected
        super().__init__(f"Invalid `{field_name}`: expected {expected}, got {value}.")


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Static agent configuration.

    Raises `AgentConfigError` at construction time if numeric limits are invalid
    or if the configured system prompt cannot be rendered.
    """

    prompt_context: PromptContext | None = None
    system_prompt: SystemPrompt = field(default_factory=SystemPrompt)
    request_options: LLMRequestOptions = field(default_factory=LLMRequestOptions)
    max_tool_iterations: int = 30

    def __post_init__(self) -> None:
        if self.max_tool_iterations < 1:
            raise AgentConfigError(
                field_name="max_tool_iterations",
                value=self.max_tool_iterations,
                expected="an integer greater than or equal to 1",
            )

        # Validate that system prompt correctly renders at agent initialization.
        render_prompt(self.system_prompt, self.prompt_context)


class Agent:
    def __init__(
        self,
        llm: LLM,
        config: AgentConfig,
        session_manager: SessionManager,
        tools: ToolConfig | None = None,
    ) -> None:
        self.llm: LLM = llm
        self._config: AgentConfig = config
        self._session_manager: SessionManager = session_manager
        self.tools: ToolConfig | None = tools
        self._instructions: str | None = render_prompt(
            self._config.system_prompt,
            self._config.prompt_context,
        )

        logger.info("agent_initialized", llm=type(llm).__name__)

    def _append_message(self, session_id: UUID, message: SessionMessage) -> None:
        """Append a message to the session."""
        self._session_manager.append_message(session_id, message)

    def _append_assistant_message(
        self,
        session_id: UUID,
        *,
        content: str,
        thinking_content: str,
        tool_calls: list[ToolCall],
        completed_response: LLMResponseCompleted | None,
    ) -> None:
        if not (content or thinking_content or tool_calls):
            return
        self._append_message(
            session_id,
            AssistantMessage(
                content=content,
                thinking_content=thinking_content,
                tool_calls=tool_calls,
                usage=(completed_response.response.usage if completed_response else None),
            ),
        )

    @staticmethod
    def _process_response_completed(
        event: LLMResponseCompleted,
        response_chunks: list[str],
        pending_tool_calls: list[ToolCall],
    ) -> None:
        if not response_chunks and event.response.output.content:
            response_chunks.append(event.response.output.content)
        # Some streams only surface function tool calls in the terminal
        # response.completed payload, so merge any unseen calls here.
        pending_call_ids = {call.call_id for call in pending_tool_calls}
        for tool_call in event.response.output.tool_calls:
            if tool_call.call_id in pending_call_ids:
                continue
            pending_tool_calls.append(tool_call)
            pending_call_ids.add(tool_call.call_id)

    def _process_event(  # noqa: C901 - allow complex
        self,
        event: LLMEvent,
        response_chunks: list[str],
        thinking_chunks: list[str],
        pending_tool_calls: list[ToolCall],
    ) -> list[LLMEvent]:
        if isinstance(event, LLMTextDelta):
            response_chunks.append(event.text)
            return [event]
        if isinstance(event, LLMThinkingDelta):
            thinking_chunks.append(event.text)
            return [event]
        if isinstance(event, LLMToolCallRequested):
            pending_tool_calls.append(event.call)
            return [event]
        if isinstance(event, (LLMToolStarted, LLMToolCompleted, LLMToolCallResult)):
            return [event]
        if isinstance(event, LLMResponseCompleted):
            self._process_response_completed(event, response_chunks, pending_tool_calls)
            return [event]
        return []

    async def _process_events(
        self,
        stream: AsyncIterator[LLMEvent],
        response_chunks: list[str],
        thinking_chunks: list[str],
        pending_tool_calls: list[ToolCall],
    ) -> AsyncIterator[LLMEvent]:
        async for event in stream:
            for processed_event in self._process_event(
                event,
                response_chunks,
                thinking_chunks,
                pending_tool_calls,
            ):
                yield processed_event

    async def _handle_tool_calls(
        self, session_id: UUID, tool_calls: list[ToolCall]
    ) -> AsyncIterator[LLMToolCallResult]:
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
                yield LLMToolCallResult(
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
            yield LLMToolCallResult(
                tool_name=tool_call.tool_name,
                result=tool_result,
            )

    async def _run_iteration(
        self,
        session_id: UUID,
        tool_definitions: list[ToolDefinition] | None,
        pending_tool_calls: list[ToolCall],
    ) -> AsyncIterator[LLMEvent]:
        """Run a single iteration, streaming events as they occur."""
        session = self._session_manager.get_session(session_id)
        request = LLMRequest(
            messages=session.messages,
            instructions=self._instructions,
            tools=tool_definitions,
            options=self._config.request_options,
        )
        stream = self.llm.generate_stream(request)
        completed_response: LLMResponseCompleted | None = None
        response_chunks: list[str] = []
        thinking_chunks: list[str] = []

        async for event in self._process_events(
            stream,
            response_chunks,
            thinking_chunks,
            pending_tool_calls,
        ):
            if isinstance(event, LLMResponseCompleted):
                completed_response = event
            yield event

        content = "".join(response_chunks)
        thinking_content = "".join(thinking_chunks)
        self._append_assistant_message(
            session_id,
            content=content,
            thinking_content=thinking_content,
            tool_calls=pending_tool_calls,
            completed_response=completed_response,
        )

        if pending_tool_calls:
            logger.info("tool_calls_pending", count=len(pending_tool_calls))
            async for event in self._handle_tool_calls(session_id, tool_calls=pending_tool_calls):
                yield event

    async def run(self, user_text: str) -> AsyncIterator[LLMEvent]:
        logger.info("agent_run_started")

        # validate user input
        if not user_text or not user_text.strip():
            logger.warning("run_called_with_empty_message")
            raise llm_exceptions.EmptyMessageError

        session_id = self._session_manager.active_session.session_id
        self._append_message(session_id, UserMessage(content=user_text.strip()))

        tool_definitions = self.tools.registry.get_definitions() if self.tools else None

        for iteration in range(1, self._config.max_tool_iterations + 1):
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

        logger.error("max_iterations_exceeded", max_iterations=self._config.max_tool_iterations)
        raise tool_exceptions.MaxIterationsExceededError(self._config.max_tool_iterations)

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
