from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from structlog import get_logger

from koda.agent.events import (
    AgentEvent,
    AgentIterationStarted,
    AgentResponseCompleted,
    AgentToolCompleted,
    AgentToolResultReady,
    AgentToolStarted,
    AgentTurnCompleted,
    AgentTurnStarted,
)
from koda.agent.stream import AgentStreamAccumulator
from koda.context import ContextManager
from koda.llm import LLMRequest, LLMRequestOptions
from koda.llm.types import LLMResponseCompleted
from koda.messages import AssistantMessage, InterruptionMessage, ToolMessage, UserMessage
from koda.prompts import SystemPromptLoader
from koda.tools import ToolConfig, ToolOutput, ToolResult
from koda.tools.executor import ToolExecutor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from koda.agent.hooks import Hook
    from koda.llm import LLM
    from koda.sessions import Session
    from koda.sessions.session import SessionMessage
    from koda.tools import ToolCall

logger = get_logger(__name__)


class Agent:
    """A Koda agent working in ``workspace``: the built-in tools, the workspace's
    ``SYSTEM.md`` (or ``~/.koda``'s, or the default prompt), and its ``AGENTS.md``.

    Messages go into ``session``; ``hooks`` run each time it changes.
    """

    def __init__(
        self,
        llm: LLM,
        *,
        session: Session,
        workspace: Path | None = None,
        hooks: Sequence[Hook] = (),
        options: LLMRequestOptions | None = None,
    ) -> None:
        self.llm = llm
        self.session = session
        self.workspace = (workspace or Path.cwd()).resolve()
        self.hooks = tuple(hooks)
        self.options = options or LLMRequestOptions()
        self.tools = ToolConfig.builtins(cwd=self.workspace, sandbox_dir=self.workspace)
        self.instructions = ContextManager.from_workspace(self.workspace).build_system_prompt(
            SystemPromptLoader.for_workspace(self.workspace).load()
        )
        self._response: AgentStreamAccumulator | None = None  # The response streaming in.
        self._unanswered: list[ToolCall] = []  # Tool calls still waiting for a result.
        logger.info("agent_initialized", llm=type(llm).__name__)

    async def run(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send ``text`` and stream the turn. An interrupted turn is kept in the session as
        the model left it; a failed one isn't, and its error goes on to the caller."""
        text = text.strip()
        if not text:
            raise ValueError("Message cannot be empty")
        try:
            async for event in self._turn(text):
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            await self._add(
                *self._partial_response(), *self._answers(_INTERRUPTED), InterruptionMessage()
            )
            raise
        except Exception:
            await self._add(*self._answers(_FAILED))
            raise
        finally:
            self._response = None

    async def _add(self, *messages: SessionMessage) -> None:
        """Add ``messages`` to the session: a checkpoint for the hooks."""
        if not messages:
            return
        for message in messages:
            self.session.add(message)
        for hook in self.hooks:
            await hook.on_checkpoint(self.session)

    async def _turn(self, text: str) -> AsyncIterator[AgentEvent]:  # noqa: C901 - the loop in one place
        """The turn: model calls until one asks for no tools, running the tools between."""
        session_id = self.session.session_id
        await self._add(UserMessage(content=text))
        yield AgentTurnStarted(session_id=session_id)
        definitions = self.tools.registry.get_definitions()
        iteration = 0
        while True:
            iteration += 1
            yield AgentIterationStarted(session_id=session_id, iteration=iteration)
            request = LLMRequest(
                messages=self.session.messages,
                instructions=self.instructions.render(),
                tools=definitions,
                options=self.options,
            )
            self._response = AgentStreamAccumulator()
            async for event in self._response.process_stream(self.llm.generate_stream(request)):
                if not isinstance(event, LLMResponseCompleted):  # The agent completes it below.
                    yield event
            calls, message = self._response.tool_calls, _response(self._response)
            self._response = None
            if message is not None:
                await self._add(message)
                yield AgentResponseCompleted(message=message)
            if not calls:
                logger.info("run_completed", iterations=iteration)
                yield AgentTurnCompleted(session_id=session_id, iterations=iteration)
                return
            self._unanswered = list(calls)
            async for event in self._run_tools(calls):
                yield event

    def _partial_response(self) -> list[SessionMessage]:
        """What the model had written of the response streaming in, if anything."""
        response = self._response
        if response is None or not (response.content or response.thinking_content):
            return []
        return [
            AssistantMessage(content=response.content, thinking_content=response.thinking_content)
        ]

    def _answers(self, reason: str) -> list[SessionMessage]:
        """An error result for each tool call left without one: a model expects a result for
        every call it made."""
        output = ToolOutput(is_error=True, error_message=reason)
        answers: list[SessionMessage] = [
            ToolMessage(
                tool_name=call.tool_name,
                tool_result=ToolResult(call_id=call.call_id, output=output),
            )
            for call in self._unanswered
        ]
        self._unanswered = []
        return answers

    async def _run_tools(self, calls: list[ToolCall]) -> AsyncIterator[AgentEvent]:
        """Run ``calls``: each result is ready as soon as it is, and is added to the session in
        call order."""
        for call in calls:
            yield AgentToolStarted(call=call)
        results: dict[str, ToolResult] = {}
        executor = ToolExecutor(self.tools.registry)
        async for call, result in executor.execute_calls(calls, self.tools.context):
            results[call.call_id] = result
            yield AgentToolResultReady(tool_name=call.tool_name, result=result)
        for call in calls:
            result = results[call.call_id]
            await self._add(ToolMessage(tool_name=call.tool_name, tool_result=result))
            self._unanswered.remove(call)
            yield AgentToolCompleted(tool_name=call.tool_name, result=result)


_INTERRUPTED = "Interrupted by the user"
_FAILED = "Not run: the turn failed"


def _response(accumulator: AgentStreamAccumulator) -> AssistantMessage | None:
    """The assistant message one model call produced, if it produced anything."""
    if not (accumulator.content or accumulator.thinking_content or accumulator.tool_calls):
        return None
    completed = accumulator.completed_response
    return AssistantMessage(
        content=accumulator.content,
        thinking_content=accumulator.thinking_content,
        tool_calls=accumulator.tool_calls,
        usage=completed.response.usage if completed else None,
    )
