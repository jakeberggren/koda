from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_service.exceptions import ServiceAuthenticationError
from koda_service.types import (
    ProviderToolStarted,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    ToolCallRequested,
)
from koda_tui.app.response import ResponseLifecycle

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_tui.state import AppState

log = get_logger(__name__)


class StreamProcessor:
    """Process provider streams with spinner and error handling."""

    def __init__(
        self,
        *,
        state: AppState,
        invalidate: Callable[[], None],
    ) -> None:
        self._state = state
        self._invalidate = invalidate
        self._lifecycle = ResponseLifecycle(state)
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

    def _handle_event(
        self,
        event: StreamEvent,
    ) -> None:
        if isinstance(event, TextDelta):
            self._lifecycle.append_content(event.text)
            return
        if isinstance(event, ThinkingDelta):
            self._lifecycle.append_thinking(event.text)
            return
        if isinstance(event, ToolCallRequested | ProviderToolStarted):
            self._lifecycle.transition_to_tool(event.call)
            return
        self._lifecycle.complete_tool(
            call_id=event.result.call_id,
            display=event.result.output.display,
            is_error=event.result.output.is_error,
            error_message=event.result.output.error_message,
        )

    async def _process_stream(self, message: str, service: KodaService) -> None:
        async for event in service.chat(message):
            self._handle_event(event)
            self._invalidate()

    async def stream(self, text: str, service: KodaService) -> None:
        """Stream a message and process the full response lifecycle."""
        self._lifecycle.begin(text)
        self._invalidate()

        try:
            self._start_spinner()
            self._streaming_task = asyncio.create_task(self._process_stream(text, service))
            await self._streaming_task
        except asyncio.CancelledError:
            pass
        except ServiceAuthenticationError:
            provider = self._state.provider_name
            error_msg = (
                f"\n\n**Authentication failed for {provider.title()}.**\n\n"
                f"Please check your API key. Press `Ctrl+P` → `Connect Provider` to update it."
            )
            self._lifecycle.append_content(error_msg)
        except Exception:
            log.exception(
                "stream_processing_failed",
                provider=self._state.provider_name,
                model=self._state.model_name,
            )
            error_msg = "An unexpected error occurred while processing the response."
            self._lifecycle.append_content(error_msg)
        finally:
            await self._stop_spinner()
            self._lifecycle.end()
            self._streaming_task = None
            self._invalidate()

    def cancel_stream(self) -> None:
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
