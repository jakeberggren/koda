from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from koda_service import ChatRequest
from koda_service.exceptions import ServiceChatError

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_tui.app.conversation import Conversation


def _render_stream_error(error: ServiceChatError) -> str:
    summary = error.summary
    detail = error.detail or "Complete the required setup and try again."
    return f"\n\n**{summary}**\n\n{detail}"


class StreamProcessor:
    """Process provider streams with spinner and error handling."""

    def __init__(
        self,
        *,
        conversation: Conversation,
        invalidate: Callable[[], None],
    ) -> None:
        self._conversation = conversation
        self._invalidate = invalidate
        self._spinner_task: asyncio.Task | None = None
        self._streaming_task: asyncio.Task | None = None

    async def _run_spinner(self) -> None:
        while True:
            await asyncio.sleep(0.1)
            self._invalidate()

    def _start_spinner(self) -> None:
        if self._spinner_task is None:
            self._spinner_task = asyncio.create_task(self._run_spinner())

    async def _stop_spinner(self) -> None:
        if self._spinner_task:
            self._spinner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._spinner_task
            self._spinner_task = None

    async def _finish_stream(self, error: str | None) -> None:
        await self._stop_spinner()
        self._conversation.end(error)
        self._streaming_task = None
        self._invalidate()

    async def _process_stream(self, message: str, service: KodaService) -> None:
        async for event in service.chat(ChatRequest(message=message)):
            self._conversation.apply(event)
            self._invalidate()

    async def stream(
        self,
        text: str,
        service: KodaService,
    ) -> None:
        """Stream the response to ``text`` into the conversation."""
        self._conversation.start(text)
        self._invalidate()

        error_text = None
        try:
            self._start_spinner()
            self._streaming_task = asyncio.create_task(self._process_stream(text, service))
            await self._streaming_task
        except asyncio.CancelledError:
            pass
        except ServiceChatError as error:
            error_text = _render_stream_error(error)
        finally:
            await self._finish_stream(error_text)

    def cancel_stream(self) -> None:
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
