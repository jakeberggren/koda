from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agent.events import (
    AgentEvent,
    AgentIterationStarted,
    AgentResponseCompleted,
    AgentTextDelta,
    AgentThinkingDelta,
    AgentToolCallRequested,
    AgentToolCompleted,
    AgentToolResultReady,
    AgentToolStarted,
    AgentTurnCompleted,
    AgentTurnStarted,
)
from koda.agent.stream import AgentStreamAccumulator
from koda.llm import LLM, LLMRequest
from koda.llm import exceptions as llm_exceptions
from koda.llm.types import (
    LLMEvent,
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.messages import AssistantMessage, ToolMessage, UserMessage
from koda.tools import ToolCall, ToolOutput, ToolResult
from koda.tools import exceptions as tool_exceptions
from koda.tools.executor import ToolExecutor
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from koda.agent.agent import AgentConfig
    from koda.sessions import SessionManager
    from koda.tools import ToolConfig, ToolDefinition

logger = get_logger(__name__)


class ToolRunner:
    """Run requested tool calls and persist their results."""

    def __init__(self, session_manager: SessionManager, tools: ToolConfig | None) -> None:
        """Create a runner for the agent-level tool execution boundary."""
        self.session_manager = session_manager
        self.tools = tools

    async def run(  # noqa: C901 - keep tool execution flow in one place
        self,
        session_id: UUID,
        tool_calls: list[ToolCall],
    ) -> AsyncIterator[AgentToolStarted | AgentToolResultReady | AgentToolCompleted]:
        """Execute tool calls, append tool messages, and stream tool result events."""
        if self.tools is None:
            logger.warning("tool_calls_requested_but_no_tools_configured", count=len(tool_calls))
            for tool_call in tool_calls:
                yield AgentToolStarted(call=tool_call)
                # Defensively handle unexpected tool calls when no tools are configured.
                tool_output = ToolOutput(is_error=True, error_message="No tools configured")
                tool_result = ToolResult(call_id=tool_call.call_id, output=tool_output)
                tool_message = ToolMessage(tool_name=tool_call.tool_name, tool_result=tool_result)
                self.session_manager.append_message(session_id, tool_message)

                yield AgentToolCompleted(
                    tool_name=tool_call.tool_name,
                    result=tool_result,
                )
            return

        executor = ToolExecutor(self.tools.registry)
        for tool_call in tool_calls:
            yield AgentToolStarted(call=tool_call)

        tool_results_by_call_id: dict[str, ToolResult] = {}
        async for tool_call, tool_result in executor.execute_calls(
            tool_calls,
            self.tools.context,
        ):
            tool_results_by_call_id[tool_call.call_id] = tool_result
            yield AgentToolResultReady(tool_name=tool_call.tool_name, result=tool_result)

        for tool_call in tool_calls:
            tool_result = tool_results_by_call_id[tool_call.call_id]
            tool_message = ToolMessage(tool_name=tool_call.tool_name, tool_result=tool_result)
            self.session_manager.append_message(session_id, tool_message)

            yield AgentToolCompleted(
                tool_name=tool_call.tool_name,
                result=tool_result,
            )


class AgentRunner:
    """Orchestrate agent turns across model iterations and tool calls."""

    def __init__(
        self,
        *,
        llm: LLM,
        config: AgentConfig,
        session_manager: SessionManager,
        tools: ToolConfig | None = None,
    ) -> None:
        """Create a runner for one stateful agent conversation."""
        self.llm = llm
        self.config = config
        self.session_manager = session_manager
        self.tools = tools
        self.tool_runner = ToolRunner(session_manager=session_manager, tools=tools)

    def _ensure_active_session_id(self) -> UUID:
        """Return the active session id, creating a session when needed."""
        session = self.session_manager.active_session
        if session is not None:
            return session.session_id
        return self.session_manager.create_session().session_id

    def _get_tool_definitions(self) -> list[ToolDefinition] | None:
        """Return provider-facing tool definitions for the configured tools."""
        return self.tools.registry.get_definitions() if self.tools else None

    def _append_assistant_message(
        self,
        session_id: UUID,
        *,
        accumulator: AgentStreamAccumulator,
    ) -> AssistantMessage | None:
        """Persist the assistant output collected during one model iteration."""
        if not (accumulator.content or accumulator.thinking_content or accumulator.tool_calls):
            return None
        completed_response = accumulator.completed_response
        usage = completed_response.response.usage if completed_response else None
        assistant_message = AssistantMessage(
            content=accumulator.content,
            thinking_content=accumulator.thinking_content,
            tool_calls=accumulator.tool_calls,
            usage=usage,
        )
        self.session_manager.append_message(session_id, assistant_message)
        return assistant_message

    def resolve_instructions(self) -> str | None:
        """Render the configured system prompt."""
        return self.config.system_prompt.render()

    def _build_request(
        self,
        session_id: UUID,
        tool_definitions: list[ToolDefinition] | None,
    ) -> LLMRequest:
        """Build the model request for the current session state."""
        session = self.session_manager.get_session(session_id)
        instructions = self.resolve_instructions()
        return LLMRequest(
            messages=session.messages,
            instructions=instructions,
            tools=tool_definitions,
            options=self.config.request_options,
        )

    @staticmethod
    def _map_llm_tool_event(event: LLMEvent) -> AgentEvent | None:
        """Map model tool stream events into agent stream events."""
        if isinstance(event, LLMToolCallRequested):
            return AgentToolCallRequested(call=event.call)
        if isinstance(event, LLMToolStarted):
            return AgentToolStarted(call=event.call)
        if isinstance(event, LLMToolCompleted):
            return AgentToolCompleted(tool_name=event.tool_name, result=event.result)
        return None

    @staticmethod
    def _map_llm_event(event: LLMEvent) -> AgentEvent | None:
        """Map model stream events into agent stream events."""
        if isinstance(event, LLMTextDelta):
            return AgentTextDelta(text=event.text)
        if isinstance(event, LLMThinkingDelta):
            return AgentThinkingDelta(text=event.text)
        return AgentRunner._map_llm_tool_event(event)

    async def run(self, user_text: str) -> AsyncIterator[AgentEvent]:  # noqa: C901 - allow complex
        """Run one user turn, repeating model calls until no tools are requested."""
        logger.info("agent_run_started")

        user_text = user_text.strip()
        if not user_text:
            logger.warning("run_called_with_empty_message")
            raise llm_exceptions.EmptyMessageError

        session_id = self._ensure_active_session_id()
        yield AgentTurnStarted(session_id=session_id)
        self.session_manager.append_message(session_id, UserMessage(content=user_text))
        tool_definitions = self._get_tool_definitions()

        for iteration in range(1, self.config.max_tool_iterations + 1):
            logger.info("agent_loop_iteration", iteration=iteration)
            yield AgentIterationStarted(session_id=session_id, iteration=iteration)

            request = self._build_request(session_id=session_id, tool_definitions=tool_definitions)
            accumulator = AgentStreamAccumulator()

            async for event in accumulator.process_stream(self.llm.generate_stream(request)):
                agent_event = self._map_llm_event(event)
                if agent_event is not None:
                    yield agent_event

            assistant_message = self._append_assistant_message(
                session_id,
                accumulator=accumulator,
            )
            if assistant_message is not None:
                yield AgentResponseCompleted(message=assistant_message)

            if not accumulator.tool_calls:
                logger.info("run_completed", iterations=iteration)
                yield AgentTurnCompleted(session_id=session_id, iterations=iteration)
                return

            logger.info("tool_calls_pending", count=len(accumulator.tool_calls))
            async for event in self.tool_runner.run(
                session_id=session_id,
                tool_calls=accumulator.tool_calls,
            ):
                yield event

        logger.error("max_iterations_exceeded", max_iterations=self.config.max_tool_iterations)
        raise tool_exceptions.MaxIterationsExceededError(self.config.max_tool_iterations)
