from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from koda_service.exceptions import (
    ServiceAuthenticationError,
    ServiceChatError,
    ServiceConnectionError,
    ServiceProviderError,
    ServiceRateLimitError,
)
from koda_tui.app.response import ResponseLifecycle

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_tui.state import AppState


def _format_stream_error(title: str, detail: str) -> str:
    return f"\n\n**{title}**\n\n{detail}"


def _render_stream_error(error: ServiceChatError, *, provider: str) -> str:
    provider_name = provider.title()

    match error:
        case ServiceAuthenticationError():
            title = f"Authentication failed for {provider_name}."
            detail = "Please check your API key. Press `Ctrl+P` → `Connect Provider` to update it."
        case ServiceRateLimitError():
            title = f"Rate limit exceeded for {provider_name}."
            detail = f"{error.message}\n\nPlease check your plan and billing details."
        case ServiceConnectionError():
            title = f"Connection error with {provider_name}."
            detail = f"{error.message}\n\nPlease check your internet connection and try again."
        case ServiceProviderError():
            title = f"Provider error from {provider_name}."
            detail = error.message
        case _:
            title = f"Unexpected error with {provider_name}."
            detail = error.message

    return _format_stream_error(title, detail)


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

    async def _finish_stream(self) -> None:
        await self._stop_spinner()
        self._lifecycle.end()
        self._streaming_task = None
        self._invalidate()

    async def _process_stream(self, message: str, service: KodaService) -> None:
        async for event in service.chat(message):
            self._lifecycle.apply_event(event)
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
        except ServiceChatError as error:
            self._lifecycle.append_content(
                _render_stream_error(error, provider=self._state.provider_name)
            )
        finally:
            await self._finish_stream()

    def cancel_stream(self) -> None:
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
