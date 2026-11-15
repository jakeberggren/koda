"""Tests for the Outbox: sending now, queueing, steering, taking a message back, and
cancelling."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from koda.agent import LLMTextDelta
from koda_tui.outbox import Outbox
from koda_tui.state import PendingInput

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from koda_tui.state import AppState


class _Agent:
    """Replies to each message, then holds the response open until released."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.released = asyncio.Event()
        self.active = 0
        self.most_active = 0

    async def run(self, text: str) -> AsyncIterator[LLMTextDelta]:
        self.sent.append(text)
        self.active += 1
        self.most_active = max(self.most_active, self.active)
        try:
            yield LLMTextDelta(text=f"reply to {text}")
            await self.released.wait()
        finally:
            self.active -= 1


@pytest.fixture
def agent() -> _Agent:
    return _Agent()


@pytest.fixture
def outbox(state: AppState, agent: _Agent) -> Outbox:
    return Outbox(state=state, respond=agent.run, invalidate=lambda: None)


async def _until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(1):
        while not condition():  # noqa: ASYNC110 - state set by other tasks, no event to wait on
            await asyncio.sleep(0.01)


def _queue(state: AppState) -> list[str]:
    """The queue as text, steers marked."""
    return [f"steer: {item.text}" if item.steer else item.text for item in state.pending_inputs]


async def test_sends_right_away_when_idle(state: AppState, agent: _Agent, outbox: Outbox) -> None:
    outbox.submit("hello", steer=False)
    assert _queue(state) == []  # Never shown as queued.
    await _until(lambda: agent.sent == ["hello"])


async def test_a_message_isnt_taken_while_koda_cant_respond(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    state.issue = "Provider setup required"

    assert not outbox.submit("hello", steer=False)
    assert _queue(state) == []
    assert agent.sent == []


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_messages_are_ignored(state: AppState, outbox: Outbox, text: str) -> None:
    outbox.submit(text, steer=False)
    outbox.submit(text, steer=True)
    assert _queue(state) == []


async def test_queued_messages_follow_the_response_in_order(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: outbox.responding)
    outbox.submit("second", steer=False)
    outbox.submit("third", steer=False)
    assert _queue(state) == ["second", "third"]

    agent.released.set()
    await _until(lambda: agent.sent == ["first", "second", "third"])
    assert _queue(state) == []
    assert agent.most_active == 1  # One response at a time.


async def test_a_steer_interrupts_and_goes_before_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: outbox.responding)
    outbox.submit("queued", steer=False)
    outbox.submit("steer one", steer=True)
    outbox.submit("steer two", steer=True)
    assert _queue(state) == ["steer: steer one", "steer: steer two", "queued"]

    await _until(lambda: agent.sent[:2] == ["first", "steer one"])
    agent.released.set()
    await _until(lambda: agent.sent == ["first", "steer one", "steer two", "queued"])
    assert _queue(state) == []


async def test_take_last_takes_back_queued_messages_but_not_steers(
    state: AppState,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: outbox.responding)
    outbox.submit("queued", steer=False)
    state.pending_inputs.insert(0, PendingInput("steer", steer=True))  # Waiting to go.

    assert outbox.take_last() == "queued"
    assert outbox.take_last() is None
    assert _queue(state) == ["steer: steer"]


async def test_send_now_interrupts_and_sends_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: outbox.responding)
    outbox.submit("queued", steer=False)

    outbox.send_now()

    await _until(lambda: agent.sent == ["first", "queued"])
    assert _queue(state) == []


async def test_cancelling_the_sending_stops_it_without_sending_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: outbox.responding)
    outbox.submit("queued", steer=False)
    sending = outbox._sending  # noqa: SLF001
    assert sending is not None

    sending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await sending

    assert agent.sent == ["first"]
    assert _queue(state) == ["queued"]


async def test_stop_interrupts_and_drops_the_queue(
    state: AppState,
    agent: _Agent,
    outbox: Outbox,
) -> None:
    outbox.submit("first", steer=False)
    await _until(lambda: outbox.responding)
    outbox.submit("queued", steer=False)
    outbox.submit("steer", steer=True)

    outbox.stop()

    await _until(lambda: not outbox.responding)
    assert _queue(state) == []
    assert agent.sent == ["first"]

    agent.released.set()
    outbox.submit("next", steer=False)
    await _until(lambda: agent.sent == ["first", "next"])


async def _send(state: AppState, run: Callable[[str], AsyncIterator[LLMTextDelta]]) -> Outbox:
    """Send a message while idle, and wait for its response to end."""
    outbox = Outbox(state=state, respond=run, invalidate=lambda: None)
    assert outbox.submit("hi", steer=False)
    assert outbox._sending is not None  # noqa: SLF001
    await outbox._sending  # noqa: SLF001
    return outbox


class TestCancelling:
    """A cancelled response just ends."""

    async def test_a_cancelled_response_ends_without_an_error(self, state: AppState) -> None:
        async def run(_text: str) -> AsyncIterator[LLMTextDelta]:
            yield LLMTextDelta(text="Start")
            await asyncio.sleep(10)

        outbox = Outbox(state=state, respond=run, invalidate=lambda: None)
        outbox.submit("test", steer=False)
        await _until(lambda: outbox.responding)

        outbox.cancel()
        assert outbox._sending is not None  # noqa: SLF001
        await outbox._sending  # noqa: SLF001

        assert state.errors == []
        assert not outbox.responding
