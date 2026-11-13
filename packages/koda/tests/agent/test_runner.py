from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from koda.agent.events import (
    AgentToolCompleted,
    AgentToolResultReady,
    AgentToolStarted,
)
from koda.agent.runner import AgentRunner, ToolRunner
from koda.llm import LLMRequest, LLMResponse
from koda.llm.types import (
    LLMEvent,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.messages import AssistantMessage, ToolMessage
from koda.sessions import InMemorySessionStore, Session
from koda.tools import (
    ToolCall,
    ToolConfig,
    ToolContext,
    ToolExecutionCoordinator,
    ToolOutput,
    ToolRegistry,
    ToolResult,
)
from koda.tools.policy import ToolPolicy

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


class EmptyParams(BaseModel):
    pass


class DelayedParams(BaseModel):
    delay: float


class DelayedTool:
    name = "delayed_tool"
    description = "Completes after the requested delay"
    parameters_model = DelayedParams

    async def execute(self, params: DelayedParams, ctx: ToolContext) -> ToolOutput:
        await asyncio.sleep(params.delay)
        return ToolOutput(content={"delay": params.delay}, display=f"delay {params.delay}")


class BlockingTool:
    name = "blocking_tool"
    description = "Blocks until released"
    parameters_model = EmptyParams

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, params: EmptyParams, ctx: ToolContext) -> ToolOutput:
        self.started.set()
        await self.release.wait()
        return ToolOutput(content={"ok": True})


class HostedToolLLM:
    def __init__(self, call: ToolCall, result: ToolResult) -> None:
        self.call = call
        self.result = result

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        raise NotImplementedError

    async def generate_structured(
        self,
        request: LLMRequest,
        schema: type[BaseModel],
    ) -> LLMResponse[BaseModel]:
        raise NotImplementedError

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        yield LLMToolStarted(call=self.call)
        yield LLMToolCompleted(tool_name=self.call.tool_name, result=self.result)
        yield LLMResponseCompleted(response=LLMResponse(output=AssistantMessage()))


def _tool_context(tmp_path: Path) -> ToolContext:
    return ToolContext(
        cwd=tmp_path,
        policy=ToolPolicy.create(tmp_path),
        coordinator=ToolExecutionCoordinator(),
    )


async def _next_tool_runner_event(
    stream: AsyncIterator[AgentToolStarted | AgentToolResultReady | AgentToolCompleted],
) -> AgentToolStarted | AgentToolResultReady | AgentToolCompleted:
    return await stream.__anext__()


@pytest.mark.asyncio
async def test_tool_runner_emits_started_before_awaiting_execution(tmp_path: Path) -> None:
    registry = ToolRegistry()
    tool = BlockingTool()
    registry.register(tool)
    runner = ToolRunner(
        append=lambda _message: None,
        tools=ToolConfig(registry=registry, context=_tool_context(tmp_path)),
    )
    call = ToolCall(tool_name=tool.name, arguments={}, call_id="call_123")

    stream = runner.run([call])

    event = await stream.__anext__()

    assert event == AgentToolStarted(call=call)
    assert not tool.started.is_set()

    next_event_task = asyncio.create_task(_next_tool_runner_event(stream))
    await asyncio.wait_for(tool.started.wait(), timeout=1)
    assert not next_event_task.done()

    tool.release.set()
    result_ready = await asyncio.wait_for(next_event_task, timeout=1)

    assert isinstance(result_ready, AgentToolResultReady)
    completed = await asyncio.wait_for(_next_tool_runner_event(stream), timeout=1)
    assert isinstance(completed, AgentToolCompleted)
    assert completed.tool_name == tool.name
    assert completed.result.call_id == call.call_id


@pytest.mark.asyncio
async def test_tool_runner_streams_result_ready_before_ordered_persistence(
    tmp_path: Path,
) -> None:
    appended: list[object] = []
    registry = ToolRegistry()
    registry.register(DelayedTool())
    runner = ToolRunner(
        append=appended.append,
        tools=ToolConfig(registry=registry, context=_tool_context(tmp_path)),
    )
    slow_call = ToolCall(
        tool_name="delayed_tool",
        arguments={"delay": 0.02},
        call_id="slow",
    )
    fast_call = ToolCall(
        tool_name="delayed_tool",
        arguments={"delay": 0},
        call_id="fast",
    )

    events = [event async for event in runner.run([slow_call, fast_call])]

    assert events[0] == AgentToolStarted(call=slow_call)
    assert events[1] == AgentToolStarted(call=fast_call)
    result_ready_call_ids = [
        event.result.call_id for event in events if isinstance(event, AgentToolResultReady)
    ]
    assert result_ready_call_ids == [
        "fast",
        "slow",
    ]
    assert [event.result.call_id for event in events if isinstance(event, AgentToolCompleted)] == [
        "slow",
        "fast",
    ]
    persisted_tool_messages = [message for message in appended if isinstance(message, ToolMessage)]
    assert [message.tool_result.call_id for message in persisted_tool_messages] == [
        "slow",
        "fast",
    ]


@pytest.mark.asyncio
async def test_runner_maps_provider_hosted_tool_events() -> None:
    call = ToolCall(tool_name="web_search", arguments={"query": "koda"}, call_id="call_web")
    result = ToolResult(call_id=call.call_id, output=ToolOutput(display="result"))
    runner = AgentRunner(
        llm=HostedToolLLM(call=call, result=result),
        session=Session(),
    )

    events = [event async for event in runner.run("search")]

    assert AgentToolStarted(call=call) in events
    assert AgentToolCompleted(tool_name=call.tool_name, result=result) in events


class TextLLM:
    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        raise NotImplementedError

    async def generate_structured(
        self,
        request: LLMRequest,
        schema: type[BaseModel],
    ) -> LLMResponse[BaseModel]:
        raise NotImplementedError

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        yield LLMTextDelta(text="hi")
        yield LLMResponseCompleted(response=LLMResponse(output=AssistantMessage(content="hi")))


@pytest.mark.asyncio
async def test_runner_saves_the_session_after_each_message() -> None:
    session = Session()
    store = InMemorySessionStore()
    runner = AgentRunner(llm=TextLLM(), session=session, store=store)

    _ = [event async for event in runner.run("hello")]

    assert [message.role for message in session.messages] == ["user", "assistant"]
    assert store.get_session(session.session_id) == session


@pytest.mark.asyncio
async def test_runner_without_store_keeps_the_session_in_memory() -> None:
    session = Session()
    runner = AgentRunner(llm=TextLLM(), session=session)

    _ = [event async for event in runner.run("hello")]

    assert [message.role for message in session.messages] == ["user", "assistant"]
