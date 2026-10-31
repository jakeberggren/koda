"""Tests for the Outbox: sending now, queueing, steering, and taking a message back."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from koda.agent import AgentTextDelta
from koda_tui.messaging import Conversation, Outbox
from koda_tui.state import UserMessage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from koda_service import ChatRequest
    from koda_tui.state import AppState


class _Agent:
    """Replies to each message, then holds the response open until released."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.released = asyncio.Event()
        self.active = 0
        self.most_active = 0

    async def chat(self, request: ChatRequest) -> AsyncIterator[AgentTextDelta]:
        self.sent.append(request.message)
        self.active += 1
        self.most_active = max(self.most_active, self.active)
        try:
            yield AgentTextDelta(text=f"reply to {request.message}")
            await self.released.wait()
        finally:
            self.active -= 1


@pytest.fixture
def agent() -> _Agent:
    return _Agent()


@pytest.fixture
def outbox(state: AppState, agent: _Agent) -> Outbox:
    conversation = Conversation(state)
    return Outbox(state=state, conversation=conversation, service=agent, invalidate=lambda: None)  # type: ignore


async def _until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(1):
        while not condition():  # noqa: ASYNC110 - state set by other tasks, no event to wait on
            await asyncio.sleep(0.01)


def _said(state: AppState) -> list[str]:
    return [message.text for message in state.messages if isinstance(message, UserMessage)]


async def test_sends_right_away_when_idle(state: AppState, agent: _Agent, outbox: Outbox) -> None:
    outbox.submit("hello", steer=False)
    assert state.pending_inputs == []  # Never shown as queued.
    await _until(lambda: agent.sent == ["hello"])
    assert _said(state) == ["hello"]


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_messages_are_ignored(state: AppState, outbox: Outbox, text: str) -> None:
    outbox.submit(text, steer=False)
    outbox.submit(text, steer=True)
    assert state.pending_inputs == []


async def test_queued_messages_follow_the_response_in_order(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: state.responding)
    outbox.submit("second", steer=False)
    outbox.submit("third", steer=False)
    assert state.pending_inputs == ["second", "third"]

    agent.released.set()
    await _until(lambda: agent.sent == ["first", "second", "third"])
    assert state.pending_inputs == []
    assert agent.most_active == 1  # One response at a time.


async def test_a_steer_interrupts_and_goes_before_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: state.responding)
    outbox.submit("queued", steer=False)
    outbox.submit("steer one", steer=True)
    outbox.submit("steer two", steer=True)
    assert state.pending_inputs == ["steer one", "steer two", "queued"]

    await _until(lambda: agent.sent[:2] == ["first", "steer one"])
    agent.released.set()
    await _until(lambda: agent.sent == ["first", "steer one", "steer two", "queued"])
    assert state.pending_inputs == []


async def test_take_last_takes_back_queued_messages_but_not_steers(
    state: AppState,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: state.responding)
    outbox.submit("queued", steer=False)
    state.pending_inputs.insert(0, "steer")  # As if a steer were waiting to go.
    outbox._steers = 1  # noqa: SLF001

    assert outbox.take_last() == "queued"
    assert outbox.take_last() is None
    assert state.pending_inputs == ["steer"]


async def test_send_now_interrupts_and_sends_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: state.responding)
    outbox.submit("queued", steer=False)

    outbox.send_now()

    await _until(lambda: agent.sent == ["first", "queued"])
    assert state.pending_inputs == []


async def test_cancelling_the_sending_stops_it_without_sending_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: state.responding)
    outbox.submit("queued", steer=False)
    sending = outbox._sending  # noqa: SLF001
    assert sending is not None

    sending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await sending

    assert agent.sent == ["first"]
    assert state.pending_inputs == ["queued"]
