"""Outbox: what happens to a message once it's written."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from koda_tui.state import PendingInput

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from koda.agent import AgentEvent
    from koda_tui.state import AppState


class Outbox:
    """Sends a message now if Koda is idle; while it responds, queues the message to
    follow the response, or steers with it: the response is interrupted and the message
    goes next. The queue is ``state.pending_inputs``, steers at its front.
    """

    def __init__(
        self,
        *,
        state: AppState,
        respond: Callable[[str], AsyncIterator[AgentEvent]],
        invalidate: Callable[[], None],
    ) -> None:
        self._state = state
        self._respond_with = respond
        self._invalidate = invalidate
        self._sending: asyncio.Task[None] | None = None
        self._response: asyncio.Task[None] | None = None

    @property
    def responding(self) -> bool:
        """Whether a response is in flight."""
        return self._response is not None and not self._response.done()

    def submit(self, text: str, *, steer: bool) -> bool:
        """Send ``text``, or queue it or steer with it while Koda responds. Whether it was
        taken: not while something stops Koda from responding, which the status shows."""
        text = text.strip()
        if not text or self._state.issue is not None:
            return False
        queue = self._state.pending_inputs
        if steer:
            queue.insert(sum(item.steer for item in queue), PendingInput(text, steer=True))
        else:
            queue.append(PendingInput(text))
        if steer and self.responding:
            self.cancel()
        self._send_queued()
        self._invalidate()
        return True

    def send_now(self) -> None:
        """Interrupt the response, if there is one, and send what's queued."""
        if self.responding:
            self.cancel()
        self._send_queued()

    def take_last(self) -> str | None:
        """Take the last queued message back, to edit it; steers are about to go."""
        queue = self._state.pending_inputs
        if not queue or queue[-1].steer:
            return None
        text = queue.pop().text
        self._invalidate()
        return text

    def stop(self) -> None:
        """Stop the response in flight and drop what's queued, as when the session
        changes and they belonged to the one left behind."""
        self._state.pending_inputs.clear()
        self.cancel()
        self._invalidate()

    def cancel(self) -> None:
        """Stop the response in flight."""
        if self._response and not self._response.done():
            self._response.cancel()

    def _send_queued(self) -> None:
        """Start sending the queue, unless it is already being sent or Koda is busy."""
        if self.responding or (self._sending and not self._sending.done()):
            return
        if (text := self._next()) is not None:
            self._sending = asyncio.create_task(self._send_all(text))

    async def _send_all(self, text: str | None) -> None:
        """Send ``text``, then whatever is queued by the time each response ends."""
        while text is not None:
            await self._send(text)
            text = self._next()

    def _next(self) -> str | None:
        """Take the next message off the front of the queue."""
        if not self._state.pending_inputs:
            return None
        text = self._state.pending_inputs.pop(0).text
        self._invalidate()
        return text

    async def _send(self, text: str) -> None:
        """Send one message and redraw as its response comes in."""
        self._response = asyncio.create_task(self._respond(text))
        self._invalidate()
        try:
            await self._response
        except asyncio.CancelledError:
            if (task := asyncio.current_task()) and task.cancelling():
                raise  # The sending itself is cancelled, not just this response.
        finally:
            self._response = None
            self._invalidate()

    async def _respond(self, text: str) -> None:
        async for _event in self._respond_with(text):
            self._invalidate()
