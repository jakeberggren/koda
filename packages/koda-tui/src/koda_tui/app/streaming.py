from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from koda.providers.events import (
    ProviderToolCompleted,
    ProviderToolStarted,
    TextDelta,
    ToolCallRequested,
    ToolCallResult,
)
from koda.providers.exceptions import ProviderAuthenticationError
from koda.tools import ToolCall

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_tui.clients import Client
    from koda_tui.state import AppState


class StreamProcessor:
    """Process provider streams and manage UI spinner updates."""

    def __init__(
        self,
        *,
        state: AppState,
        invalidate: Callable[[], None],
    ) -> None:
        self._state = state
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

    async def _process_stream(self, message: str, client: Client) -> None:  # noqa: C901 - allow complex
        async for event in client.chat(message):
            if isinstance(event, TextDelta):
                await self._stop_spinner()
                self._state.append_delta(event.text)
            elif isinstance(event, ToolCallRequested):
                self._state.transition_to_tool(event.call)
            elif isinstance(event, ProviderToolStarted):
                call = ToolCall(tool_name=event.tool_name, call_id=event.call_id, arguments={})
                self._state.transition_to_tool(call)
            elif isinstance(event, ToolCallResult):
                self._state.complete_tool_message(
                    event.result.call_id,
                    event.result.output.display,
                    is_error=event.result.output.is_error,
                )
            elif isinstance(event, ProviderToolCompleted):
                self._state.complete_tool_message(
                    event.call_id,
                    event.display,
                    is_error=event.is_error,
                )
            self._invalidate()

    async def stream(self, text: str, client: Client) -> None:
        """Stream a message and process the full response lifecycle."""
        self._state.begin_response(text)
        self._invalidate()

        try:
            self._start_spinner()
            self._streaming_task = asyncio.create_task(self._process_stream(text, client))
            await self._streaming_task
        except asyncio.CancelledError:
            pass
        except ProviderAuthenticationError:
            provider = self._state.provider_name
            error_msg = (
                f"\n\n**Authentication failed for {provider.title()}.**\n\n"
                f"Please check your API key. Press `Ctrl+P` → `Connect Provider` to update it."
            )
            self._state.append_delta(error_msg)
        except Exception as e:
            error_msg = f"\n\n**Error:** {type(e).__name__}: {e}"
            self._state.append_delta(error_msg)
        finally:
            await self._stop_spinner()
            self._state.end_response()
            self._streaming_task = None
            self._invalidate()

    def cancel_stream(self) -> None:
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
