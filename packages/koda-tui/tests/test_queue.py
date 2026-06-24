from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from koda_tui.app.queue import MessageQueue

if TYPE_CHECKING:
    from koda_tui.state import AppState


@dataclass(slots=True)
class QueueHarness:
    state: AppState
    sent: list[str] = field(default_factory=list)
    invalidations: int = 0
    cancellations: int = 0
    block_sends: bool = False
    active_sends: int = 0
    max_active_sends: int = 0
    send_started: asyncio.Event = field(default_factory=asyncio.Event)
    send_released: asyncio.Event = field(default_factory=asyncio.Event)
    sent_changed: asyncio.Event = field(default_factory=asyncio.Event)

    def create_queue(self) -> MessageQueue:
        return MessageQueue(
            state=self.state,
            send_message=self.send_message,
            invalidate=self.invalidate,
            cancel_streaming=self.cancel_streaming,
        )

    async def send_message(self, text: str) -> None:
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        try:
            self.sent.append(text)
            self.sent_changed.set()
            self.send_started.set()
            if self.block_sends:
                await self.send_released.wait()
        finally:
            self.active_sends -= 1

    def invalidate(self) -> None:
        self.invalidations += 1

    def cancel_streaming(self) -> None:
        self.cancellations += 1


async def _wait_for_sent(harness: QueueHarness, expected: list[str]) -> None:
    async with asyncio.timeout(1):
        while harness.sent != expected:
            harness.sent_changed.clear()
            if harness.sent != expected:
                await harness.sent_changed.wait()


@pytest.fixture
def queue_harness(state: AppState) -> QueueHarness:
    return QueueHarness(state=state)


@pytest.mark.asyncio
async def test_enqueue_drains_visible_queue_fifo_when_idle(
    queue_harness: QueueHarness,
) -> None:
    queue = queue_harness.create_queue()

    queue.enqueue(" first ")
    queue.enqueue("second")
    await _wait_for_sent(queue_harness, ["first", "second"])

    assert queue_harness.sent == ["first", "second"]
    assert queue_harness.state.pending_inputs == []
    assert queue_harness.cancellations == 0
    assert queue_harness.invalidations == 4


@pytest.mark.asyncio
async def test_enqueue_waits_while_streaming(queue_harness: QueueHarness) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True

    queue.enqueue("first")
    queue.enqueue("second")

    assert queue_harness.sent == []
    assert queue_harness.state.pending_inputs == ["first", "second"]
    assert queue_harness.cancellations == 0
    assert queue_harness.invalidations == 2


@pytest.mark.parametrize("text", ["", " ", "\n\t"])
def test_blank_messages_are_ignored(queue_harness: QueueHarness, text: str) -> None:
    queue = queue_harness.create_queue()

    queue.enqueue(text)
    queue.steer(text)

    assert queue_harness.sent == []
    assert queue_harness.state.pending_inputs == []
    assert queue_harness.invalidations == 0
    assert queue_harness.cancellations == 0


def test_dequeue_all_clears_visible_queue_once(queue_harness: QueueHarness) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True
    queue.enqueue("first")
    queue.enqueue("second")

    queue.dequeue_all()

    assert queue_harness.state.pending_inputs == []
    assert queue.pop_last() is None
    assert queue_harness.invalidations == 3

    queue.dequeue_all()
    assert queue_harness.invalidations == 3


@pytest.mark.asyncio
async def test_steer_sends_next_without_adding_to_visible_queue(
    queue_harness: QueueHarness,
) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True

    queue.enqueue("queued")
    queue.steer(" steer ")

    assert queue_harness.cancellations == 1
    assert queue_harness.state.pending_inputs == ["queued"]
    assert queue_harness.sent == []

    queue_harness.state.is_streaming = False
    queue.kick()
    await _wait_for_sent(queue_harness, ["steer", "queued"])

    assert queue_harness.sent == ["steer", "queued"]
    assert queue_harness.state.pending_inputs == []


@pytest.mark.asyncio
async def test_steer_sends_immediately_when_idle(queue_harness: QueueHarness) -> None:
    queue = queue_harness.create_queue()

    queue.steer("steer")
    await _wait_for_sent(queue_harness, ["steer"])

    assert queue_harness.sent == ["steer"]
    assert queue_harness.state.pending_inputs == []
    assert queue_harness.cancellations == 0
    assert queue_harness.invalidations == 0


@pytest.mark.asyncio
async def test_multiple_steers_are_fifo_and_precede_visible_queue(
    queue_harness: QueueHarness,
) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True
    queue.enqueue("queued")

    queue.steer("steer one")
    queue.steer("steer two")

    assert queue_harness.cancellations == 2
    queue_harness.state.is_streaming = False
    queue.kick()
    await _wait_for_sent(queue_harness, ["steer one", "steer two", "queued"])

    assert queue_harness.state.pending_inputs == []


@pytest.mark.asyncio
async def test_kick_serializes_sends_and_includes_messages_enqueued_mid_drain(
    queue_harness: QueueHarness,
) -> None:
    queue = queue_harness.create_queue()
    queue_harness.block_sends = True

    queue.enqueue("first")
    await asyncio.wait_for(queue_harness.send_started.wait(), timeout=1)

    queue.enqueue("second")
    queue.kick()
    queue.kick()

    assert queue_harness.sent == ["first"]
    assert queue_harness.active_sends == 1
    assert queue_harness.state.pending_inputs == ["second"]

    queue_harness.send_released.set()
    await _wait_for_sent(queue_harness, ["first", "second"])

    assert queue_harness.max_active_sends == 1
    assert queue_harness.state.pending_inputs == []


def test_pop_last_edits_visible_queue_only(queue_harness: QueueHarness) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True

    queue.enqueue("first")
    queue.enqueue("second")

    assert queue.pop_last() == "second"
    assert queue_harness.state.pending_inputs == ["first"]
    assert queue.pop_last() == "first"
    assert queue_harness.state.pending_inputs == []
    assert queue.pop_last() is None
    assert queue_harness.invalidations == 4


@pytest.mark.asyncio
async def test_steer_and_drain_stops_current_stream_then_sends_visible_queue(
    queue_harness: QueueHarness,
) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True
    queue.enqueue("queued")

    queue.steer_and_drain()

    assert queue_harness.cancellations == 1
    assert queue_harness.sent == []
    assert queue_harness.state.pending_inputs == ["queued"]

    queue_harness.state.is_streaming = False
    queue.kick()
    await _wait_for_sent(queue_harness, ["queued"])

    assert queue_harness.sent == ["queued"]
    assert queue_harness.state.pending_inputs == []


@pytest.mark.asyncio
async def test_steer_and_drain_starts_queued_send_when_idle(
    queue_harness: QueueHarness,
) -> None:
    queue = queue_harness.create_queue()
    queue_harness.state.is_streaming = True
    queue.enqueue("queued")
    queue_harness.state.is_streaming = False

    queue.steer_and_drain()
    await _wait_for_sent(queue_harness, ["queued"])

    assert queue_harness.cancellations == 0
    assert queue_harness.state.pending_inputs == []
