"""Outbox: what happens to a message once it's written."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from koda.llm import exceptions as llm_exceptions
from koda.tools import exceptions as tool_exceptions
from koda_tui import strings
from koda_tui.state import ErrorMessage, PendingInput

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_tui.messaging.conversation import Conversation
    from koda_tui.runtime import Runtime
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
        conversation: Conversation,
        runtime: Runtime,
        invalidate: Callable[[], None],
    ) -> None:
        self._state = state
        self._conversation = conversation
        self._runtime = runtime
        self._invalidate = invalidate
        self._sending: asyncio.Task[None] | None = None
        self._response: asyncio.Task[None] | None = None

    def submit(self, text: str, *, steer: bool) -> None:
        """Send ``text``, or queue it or steer with it while Koda responds."""
        text = text.strip()
        if not text:
            return
        queue = self._state.pending_inputs
        if steer:
            queue.insert(sum(item.steer for item in queue), PendingInput(text, steer=True))
        else:
            queue.append(PendingInput(text))
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
        text = self._state.pending_inputs.pop(0).text
        self._invalidate()
        return text

    async def _send(self, text: str) -> None:
        """Send one message and apply its response to the conversation."""
        self._conversation.start(text)
        self._invalidate()
        error = None
        try:
            self._response = asyncio.create_task(self._respond(text))
            await self._response
        except asyncio.CancelledError:
            if (task := asyncio.current_task()) and task.cancelling():
                raise  # The sending itself is cancelled, not just this response.
        except (llm_exceptions.LLMError, tool_exceptions.ToolError) as failure:
            error = _error_message(failure)
        finally:
            self._response = None
            self._conversation.end(error)
            self._invalidate()

    async def _respond(self, text: str) -> None:
        async for event in self._runtime.run(text):
            self._conversation.apply(event)
            self._invalidate()


_ERRORS = strings.Screen.Chat.Errors

# Why a response failed and what to do about it, by error type. The first match wins, so
# subclasses come before their bases.
_ERROR_MESSAGES: tuple[tuple[type[Exception], str, str | None], ...] = (
    (llm_exceptions.LLMAuthenticationError, _ERRORS.AUTHENTICATION, _ERRORS.AUTHENTICATION_FIX),
    (llm_exceptions.LLMRateLimitError, _ERRORS.RATE_LIMIT, _ERRORS.RATE_LIMIT_FIX),
    (llm_exceptions.LLMConnectionError, _ERRORS.CONNECTION, _ERRORS.CONNECTION_FIX),
    (llm_exceptions.LLMAPIError, _ERRORS.PROVIDER, None),
    (llm_exceptions.LLMConfigurationError, _ERRORS.NOT_READY, None),
    (tool_exceptions.ToolError, _ERRORS.TOOL, None),
)


def _error_message(error: Exception) -> ErrorMessage:
    """Why a response failed, and what to do about it."""
    for kind, summary, fix in _ERROR_MESSAGES:
        if isinstance(error, kind):
            return ErrorMessage(summary, f"{error}\n\n{fix}" if fix else str(error))
    return ErrorMessage(_ERRORS.REQUEST, str(error))
