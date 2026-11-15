"""Tests for a turn: events go into the session, then to the hooks, then to the caller."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import pytest
from pydantic import BaseModel

from koda.agent import (
    Agent,
    AgentEvent,
    AgentToolCompleted,
    AgentToolResultReady,
    AgentToolStarted,
    Hook,
)
from koda.llm import LLMRequest, LLMResponse
from koda.llm.types import (
    LLMEvent,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMToolCallRequested,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.messages import (
    AssistantMessage,
    InterruptionMessage,
    TokenUsage,
    ToolCall,
    ToolMessage,
    ToolOutput,
    UserMessage,
)
from koda.sessions import InMemorySessionStore, SaveSessionHook, Session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _EmptyParams(BaseModel):
    pass


class _DelayedParams(BaseModel):
    delay: float


class _DelayedTool:
    name = "delayed_tool"
    description = "Completes after the requested delay"
    parameters_model = _DelayedParams

    async def execute(self, params: _DelayedParams) -> ToolOutput:
        await asyncio.sleep(params.delay)
        return ToolOutput(content={"delay": params.delay})


class _BlockingTool:
    name = "blocking_tool"
    description = "Blocks until released"
    parameters_model = _EmptyParams

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, params: _EmptyParams) -> ToolOutput:
        self.started.set()
        await self.release.wait()
        return ToolOutput(content={"ok": True})


class _FailingTool:
    name = "delayed_tool"
    description = "Fails"
    parameters_model = _DelayedParams

    async def execute(self, params: _DelayedParams) -> ToolOutput:
        raise RuntimeError("tool broke")


class _ScriptedLLM:
    """Streams the next script on each call: a list of events, or an error to raise."""

    def __init__(self, *scripts: list[LLMEvent] | Exception) -> None:
        self.scripts = list(scripts)

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        raise NotImplementedError

    async def generate_structured(
        self,
        request: LLMRequest,
        schema: type[BaseModel],
    ) -> LLMResponse[BaseModel]:
        raise NotImplementedError

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        script = self.scripts.pop(0)
        if isinstance(script, Exception):
            raise script
        for event in script:
            yield event


def _says(text: str) -> list[LLMEvent]:
    return [
        LLMTextDelta(text=text),
        LLMResponseCompleted(response=LLMResponse(output=AssistantMessage(content=text))),
    ]


def _calls(*calls: ToolCall) -> list[LLMEvent]:
    return [
        *(LLMToolCallRequested(call=call) for call in calls),
        LLMResponseCompleted(response=LLMResponse(output=AssistantMessage(tool_calls=list(calls)))),
    ]


class _Recorder(Hook):
    """Remembers the roles of the session's messages at each checkpoint."""

    def __init__(self) -> None:
        self.checkpoints: list[list[str]] = []

    async def on_checkpoint(self, session: Session) -> None:
        self.checkpoints.append([m.role for m in session.messages])


def _agent(llm: _ScriptedLLM, *tools: object, hooks: tuple = ()) -> Agent:
    return Agent(cast("Any", llm), tools=cast("Any", tools), hooks=hooks)


async def _run(agent: Agent, text: str = "hello") -> list[AgentEvent]:
    return [event async for event in agent.run(text)]


async def test_a_turn_is_kept_in_the_session_and_saved() -> None:
    store = InMemorySessionStore()
    agent = _agent(_ScriptedLLM(_says("hi")), hooks=(SaveSessionHook(store),))

    await _run(agent)

    session = agent.session
    assert session.messages == [UserMessage(content="hello"), AssistantMessage(content="hi")]
    assert store.get_session(session.session_id) == session


async def test_hooks_run_each_time_a_message_is_added() -> None:
    recorder = _Recorder()
    agent = _agent(_ScriptedLLM(_says("hi")), hooks=(recorder,))

    await _run(agent)

    assert recorder.checkpoints == [["user"], ["user", "assistant"]]


async def test_tools_start_before_they_run_and_complete_in_call_order() -> None:
    slow = ToolCall(tool_name="delayed_tool", arguments={"delay": 0.02}, call_id="slow")
    fast = ToolCall(tool_name="delayed_tool", arguments={"delay": 0}, call_id="fast")
    agent = _agent(_ScriptedLLM(_calls(slow, fast), _says("done")), _DelayedTool())

    events = await _run(agent)

    tool_events = [e for e in events if isinstance(e, AgentToolStarted | AgentToolResultReady)]
    assert [type(e).__name__ for e in tool_events[:2]] == ["AgentToolStarted"] * 2
    ready = [e.message.call_id for e in events if isinstance(e, AgentToolResultReady)]
    completed = [e.message.call_id for e in events if isinstance(e, AgentToolCompleted)]
    assert (ready, completed) == (["fast", "slow"], ["slow", "fast"])
    tool_messages = [m for m in agent.session.messages if isinstance(m, ToolMessage)]
    assert [m.call_id for m in tool_messages] == ["slow", "fast"]


async def test_tools_the_provider_runs_are_not_kept_as_messages() -> None:
    call = ToolCall(tool_name="web_search", arguments={"query": "koda"}, call_id="web")
    found = ToolMessage(
        tool_name="web_search",
        call_id=call.call_id,
        output=ToolOutput(display="result"),
    )
    llm = _ScriptedLLM(
        [
            LLMToolStarted(call=call),
            LLMToolCompleted(message=found),
            *_says("found"),
        ],
    )
    agent = _agent(llm)

    events = await _run(agent, "search")

    assert LLMToolCompleted(message=found) in events
    assert not any(isinstance(e, AgentToolCompleted) for e in events)
    assert not any(isinstance(m, ToolMessage) for m in agent.session.messages)


async def test_an_interrupted_turn_answers_the_calls_left_running_and_says_so() -> None:
    tool = _BlockingTool()
    call = ToolCall(tool_name=tool.name, arguments={}, call_id="call")
    recorder = _Recorder()
    agent = _agent(_ScriptedLLM(_calls(call)), tool, hooks=(recorder,))

    task = asyncio.create_task(_run(agent))
    await asyncio.wait_for(tool.started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert recorder.checkpoints[-1] == ["user", "assistant", "tool", "interruption"]
    [answer] = [m for m in agent.session.messages if isinstance(m, ToolMessage)]
    assert answer.output.error_message == "Interrupted by the user"
    assert isinstance(agent.session.messages[-1], InterruptionMessage)


async def test_a_failed_turn_raises_and_leaves_the_session_as_it_was() -> None:
    agent = _agent(_ScriptedLLM(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        await _run(agent)

    assert [m.role for m in agent.session.messages] == ["user"]


async def test_a_failed_turn_answers_the_calls_it_left() -> None:
    call = ToolCall(tool_name="delayed_tool", arguments={"delay": 0}, call_id="call")
    llm = _ScriptedLLM(_calls(call), RuntimeError("boom"))
    agent = _agent(llm, _FailingTool())

    with pytest.raises(RuntimeError, match="tool broke"):
        await _run(agent)

    [answer] = [m for m in agent.session.messages if isinstance(m, ToolMessage)]
    assert answer.output.error_message == "Not run: the turn failed"


async def test_a_failing_hook_fails_the_turn() -> None:
    class _Broken(Hook):
        async def on_checkpoint(self, session: Session) -> None:
            raise OSError("disk full")

    agent = _agent(_ScriptedLLM(_says("hi")), hooks=(_Broken(),))

    with pytest.raises(OSError, match="disk full"):
        await _run(agent)


async def test_an_empty_message_is_refused() -> None:
    agent = _agent(_ScriptedLLM())

    with pytest.raises(ValueError, match="empty"):
        await _run(agent, "   ")


async def test_an_interruption_keeps_what_the_model_had_written() -> None:
    written = asyncio.Event()

    class _Stalling(_ScriptedLLM):
        async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
            yield LLMTextDelta(text="Half a")
            written.set()
            await asyncio.Event().wait()

    agent = _agent(_Stalling())
    task = asyncio.create_task(_run(agent))
    await asyncio.wait_for(written.wait(), timeout=1)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    _, partial, interruption = agent.session.messages
    assert isinstance(partial, AssistantMessage)
    assert partial.content == "Half a"
    assert isinstance(interruption, InterruptionMessage)


async def test_the_turn_holds_the_response_while_it_streams() -> None:
    llm = _ScriptedLLM(
        [
            LLMTextDelta(text="Hel"),
            LLMTextDelta(text="lo"),
            LLMResponseCompleted(response=LLMResponse(output=AssistantMessage(content="Hello"))),
        ],
    )
    agent = _agent(llm)
    live = [
        agent.turn.response.content if agent.turn.response else None
        async for event in agent.run("hi")
        if isinstance(event, LLMTextDelta)
    ]

    assert live == ["Hel", "Hello"]
    assert (agent.turn.running, agent.turn.response) == (False, None)


async def test_the_turn_holds_tool_results_until_the_session_has_them() -> None:
    slow = ToolCall(tool_name="delayed_tool", arguments={"delay": 0.02}, call_id="slow")
    fast = ToolCall(tool_name="delayed_tool", arguments={"delay": 0}, call_id="fast")
    agent = _agent(_ScriptedLLM(_calls(slow, fast), _says("done")), _DelayedTool())
    held = [
        set(agent.turn.results)
        async for event in agent.run("go")
        if isinstance(event, AgentToolResultReady)
    ]

    assert held == [{"fast"}, {"fast", "slow"}]
    assert agent.turn.results == {}


async def test_the_turn_keeps_the_tools_the_provider_ran() -> None:
    call = ToolCall(tool_name="web_search", arguments={"query": "koda"}, call_id="web")
    found = ToolMessage(
        tool_name="web_search",
        call_id=call.call_id,
        output=ToolOutput(display="result"),
    )
    started = LLMToolStarted(call=call)
    llm = _ScriptedLLM([started, LLMToolCompleted(message=found)])
    agent = _agent(llm)

    await _run(agent)

    assert agent.turn.provider_calls == [call]
    assert agent.turn.results == {"web": found}


async def test_what_the_provider_only_sends_at_the_end_is_in_the_response() -> None:
    call = ToolCall(tool_name="delayed_tool", arguments={"delay": 0}, call_id="late")
    usage = TokenUsage(input_tokens=3, output_tokens=2)
    completed = AssistantMessage(content="Unstreamed answer", tool_calls=[call])
    llm = _ScriptedLLM(
        [LLMResponseCompleted(response=LLMResponse(output=completed, usage=usage))],
        _says("ok"),
    )
    agent = _agent(llm, _DelayedTool())

    await _run(agent)

    response = agent.session.messages[1]
    assert isinstance(response, AssistantMessage)
    assert (response.content, response.tool_calls, response.usage) == (
        "Unstreamed answer",
        [call],
        usage,
    )


async def test_the_agent_keeps_one_turn_that_starts_fresh_each_time() -> None:
    call = ToolCall(tool_name="web_search", arguments={"query": "koda"}, call_id="web")
    llm = _ScriptedLLM([LLMToolStarted(call=call), *_says("found")], _says("again"))
    agent = _agent(llm)
    turn = agent.turn

    await _run(agent, "search")
    assert (agent.turn is turn, turn.running, turn.provider_calls) == (True, False, [call])

    await _run(agent, "again")
    assert (agent.turn is turn, turn.provider_calls) == (True, [])
