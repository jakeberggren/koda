"""Outbox: what happens to a message once it's written."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from koda_service import ChatRequest
from koda_service.exceptions import ServiceChatError

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_tui.messaging.conversation import Conversation
    from koda_tui.state import AppState

SPINNER_TICK = 0.1  # Seconds between redraws while responding, to animate the spinner.


class Outbox:
    """Sends a message now if Koda is idle; while it responds, queues the message to
    follow the response, or steers with it: the response is interrupted and the message
    goes next. The queue is ``state.pending_inputs``, steers at its front.
    """

    def __init__(
        self,
        *,
        state: AppState,
        conversation: Conversation,
        service: KodaService,
        invalidate: Callable[[], None],
    ) -> None:
        self._state = state
        self._conversation = conversation
        self._service = service
        self._invalidate = invalidate
        self._steers = 0  # How many messages at the front of the queue are steers.
        self._sending: asyncio.Task[None] | None = None
        self._response: asyncio.Task[None] | None = None

    def submit(self, text: str, *, steer: bool) -> None:
        """Send ``text``, or queue it or steer with it while Koda responds."""
        if not text.strip():
            return
        text = text.strip()
        queue = self._state.pending_inputs
        if steer:
            queue.insert(self._steers, text)
            self._steers += 1
        else:
            queue.append(text)
        if steer and self._state.responding:
            self.cancel()
        self._send_queued()
        self._invalidate()

    def send_now(self) -> None:
        """Interrupt the response, if there is one, and send what's queued."""
        if self._state.responding:
            self.cancel()
        self._send_queued()

    def take_last(self) -> str | None:
        """Take the last queued message back, to edit it; steers are about to go."""
        if len(self._state.pending_inputs) <= self._steers:
            return None
        text = self._state.pending_inputs.pop()
        self._invalidate()
        return text

    def cancel(self) -> None:
        """Stop the response in flight."""
        if self._response and not self._response.done():
            self._response.cancel()

    def _send_queued(self) -> None:
        """Start sending the queue, unless it is already being sent or Koda is busy."""
        if self._state.responding or (self._sending and not self._sending.done()):
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
        self._steers = max(0, self._steers - 1)
        text = self._state.pending_inputs.pop(0)
        self._invalidate()
        return text

    async def _send(self, text: str) -> None:
        """Send one message and apply its response to the conversation."""
        self._conversation.start(text)
        self._invalidate()
        error = None
        spinner = asyncio.create_task(self._tick())
        try:
            self._response = asyncio.create_task(self._respond(text))
            await self._response
        except asyncio.CancelledError:
            if (task := asyncio.current_task()) and task.cancelling():
                raise  # The sending itself is cancelled, not just this response.
        except ServiceChatError as failure:
            error = _error_text(failure)
        finally:
            spinner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await spinner
            self._response = None
            self._conversation.end(error)
            self._invalidate()

    async def _respond(self, text: str) -> None:
        async for event in self._service.chat(ChatRequest(message=text)):
            self._conversation.apply(event)
            self._invalidate()

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(SPINNER_TICK)
            self._invalidate()


def _error_text(error: ServiceChatError) -> str:
    detail = error.detail or "Complete the required setup and try again."
    return f"\n\n**{error.summary}**\n\n{detail}"
