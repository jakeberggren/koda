from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
from koda.llm.types import LLMResponseCompleted, LLMToolCompleted, LLMToolStarted
from koda.messages import AssistantMessage, InterruptionMessage, ToolMessage, UserMessage
from koda.prompts import SystemPromptLoader
from koda.tools import ToolConfig, ToolOutput, ToolResult
from koda.tools.executor import ToolExecutor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from koda.agent.hooks import Hook
    from koda.llm import LLM
    from koda.messages import Message
    from koda.sessions import Session
    from koda.tools import ToolCall

logger = get_logger(__name__)


@dataclass
class Turn:
    """The agent's latest turn, while it runs and after. Never saved: once something is
    done, it is in the session."""

    running: bool = False
    # The response streaming in, so far.
    response: AssistantMessage | None = None
    # Tool calls waiting for their result.
    calls: list[ToolCall] = field(default_factory=list)
    # Tool results that are ready, by call id, before they are added to the session in order.
    results: dict[str, ToolResult] = field(default_factory=dict)
    # Tools the provider ran itself, such as web search; they are part of its response.
    provider_calls: list[ToolCall] = field(default_factory=list)


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
        self.turn = Turn()  # The latest turn; none has run yet.
        logger.info("agent_initialized", llm=type(llm).__name__)

    async def run(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send ``text`` and stream the turn. An interrupted turn is kept in the session as
        the model left it; a failed one isn't, and its error goes on to the caller."""
        text = text.strip()
        if not text:
            raise ValueError("Message cannot be empty")
        self.turn = Turn(running=True)
        try:
            async for event in self._turn(text):
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            await self._add(
                *self._partial_response(), *self._answers(INTERRUPTED), InterruptionMessage()
            )
            raise
        except Exception:
            await self._add(*self._answers(FAILED))
            raise
        finally:
            self.turn.running = False
            self.turn.response = None

    async def _add(self, *messages: Message) -> None:
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
            accumulator = AgentStreamAccumulator()
            async for event in accumulator.process_stream(self.llm.generate_stream(request)):
                if isinstance(event, LLMResponseCompleted):
                    continue  # The agent completes the response below.
                self._follow(event, accumulator)
                yield event
            calls, message = accumulator.tool_calls, assembled_response(accumulator)
            self.turn.response = None
            if message is not None:
                await self._add(message)
                yield AgentResponseCompleted(message=message)
            if not calls:
                logger.info("run_completed", iterations=iteration)
                yield AgentTurnCompleted(session_id=session_id, iterations=iteration)
                return
            self.turn.calls = list(calls)
            async for event in self._run_tools(calls):
                yield event

    def _follow(self, event: AgentEvent, accumulator: AgentStreamAccumulator) -> None:
        """Keep the turn up to date with a model event."""
        turn = self.turn
        match event:
            case LLMToolStarted(call=call):
                turn.provider_calls.append(call)
            case LLMToolCompleted(result=result):
                turn.results[result.call_id] = result
            case _:
                turn.response = AssistantMessage(
                    content=accumulator.content,
                    thinking_content=accumulator.thinking_content,
                    tool_calls=list(accumulator.tool_calls),
                )

    def _partial_response(self) -> list[Message]:
        """What the model had written of the response streaming in, if anything."""
        response = self.turn.response
        if response is None or not (response.content or response.thinking_content):
            return []
        return [
            AssistantMessage(content=response.content, thinking_content=response.thinking_content)
        ]

    def _answers(self, reason: str) -> list[Message]:
        """An error result for each tool call left without one: a model expects a result for
        every call it made."""
        output = ToolOutput(is_error=True, error_message=reason)
        answers: list[Message] = [
            ToolMessage(
                tool_name=call.tool_name,
                tool_result=ToolResult(call_id=call.call_id, output=output),
            )
            for call in self.turn.calls
        ]
        self.turn.calls = []
        return answers

    async def _run_tools(self, calls: list[ToolCall]) -> AsyncIterator[AgentEvent]:
        """Run ``calls``: each result is ready as soon as it is, and is added to the session in
        call order."""
        for call in calls:
            yield AgentToolStarted(call=call)
        executor = ToolExecutor(self.tools.registry)
        async for call, result in executor.execute_calls(calls, self.tools.context):
            self.turn.results[call.call_id] = result
            yield AgentToolResultReady(tool_name=call.tool_name, result=result)
        for call in calls:
            result = self.turn.results.pop(call.call_id)
            await self._add(ToolMessage(tool_name=call.tool_name, tool_result=result))
            self.turn.calls.remove(call)
            yield AgentToolCompleted(tool_name=call.tool_name, result=result)


INTERRUPTED = "Interrupted by the user"
FAILED = "Not run: the turn failed"


def assembled_response(accumulator: AgentStreamAccumulator) -> AssistantMessage | None:
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
