from __future__ import annotations

import asyncio
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from koda_tui.state import AppState


class MessageQueue:
    """Manage queued messages and serialized sending."""

    def __init__(
        self,
        *,
        state: AppState,
        send_message: Callable[[str], Awaitable[None]],
        invalidate: Callable[[], None],
        cancel_streaming: Callable[[], None],
    ) -> None:
        self._state = state
        self._send_message = send_message
        self._invalidate = invalidate
        self._cancel_streaming = cancel_streaming
        self._pending_messages: deque[str] = deque()
        self._send_queue_task: asyncio.Task | None = None

    def enqueue(self, text: str, *, cancel_current: bool = False) -> None:
        """Queue a message to be sent after the current stream completes."""
        if not text or not text.strip():
            return
        cleaned = text.strip()
        self._pending_messages.append(cleaned)
        self._state.pending_inputs.append(cleaned)
        self._invalidate()
        if cancel_current and self._state.is_streaming:
            self._cancel_streaming()
        if not self._state.is_streaming:
            self.kick()

    def dequeue_all(self) -> None:
        """Remove all queued messages."""
        if not self._pending_messages:
            return
        self._pending_messages.clear()
        self._state.pending_inputs.clear()
        self._invalidate()

    def kick(self) -> None:
        """Start draining the queue if idle."""
        if self._send_queue_task and not self._send_queue_task.done():
            return
        self._send_queue_task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        while self._pending_messages and not self._state.is_streaming:
            next_message = self._pending_messages.popleft()
            if self._state.pending_inputs:
                self._state.pending_inputs.pop(0)
            self._invalidate()
            await self._send_message(next_message)
