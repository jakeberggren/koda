from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from pathlib import Path
from typing import Any

from prompt_toolkit import Application

from koda.providers.events import (
    ProviderToolCompleted,
    ProviderToolStarted,
    TextDelta,
    ToolCallRequested,
    ToolCallResult,
)
from koda.providers.exceptions import ProviderAuthenticationError
from koda.tools import ToolCall
from koda_common import SettingsManager
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.output import SynchronizedOutput
from koda_tui.clients import Client, LocalClient, MockClient
from koda_tui.state import AppState
from koda_tui.ui.layout import TUILayout
from koda_tui.ui.palette import PaletteManager
from koda_tui.ui.styles import get_style


def _create_client(settings: SettingsManager, sandbox_dir: Path) -> Client:
    """Create and configure the client."""
    if settings.use_mock_client:
        return MockClient()
    return LocalClient(settings, sandbox_dir)


class KodaTuiApp:
    """Main TUI application."""

    def __init__(
        self,
        sandbox_dir: Path | None = None,
        client: Client | None = None,
    ) -> None:
        self._sandbox_dir = sandbox_dir or Path.cwd().resolve()
        self._settings = SettingsManager.get_instance()
        self._client = client or _create_client(self._settings, self._sandbox_dir)

        # Subscribe to settings changes
        self._unsubscribe = self._settings.subscribe(self._on_settings_changed)

        # Initialize state
        self.state = AppState(
            provider_name=self._settings.provider,
            model_name=self._settings.model,
            show_scrollbar=self._settings.show_scrollbar,
            queue_inputs=self._settings.queue_inputs,
        )

        # Initialize layout
        self.layout = TUILayout(self.state)
        self.layout.renderer.set_theme(self._settings.theme)

        # Application instance (created on run)
        self._app: Application | None = None
        self._streaming_task: asyncio.Task | None = None
        self._spinner_task: asyncio.Task | None = None
        self._exit_reset_handle: asyncio.TimerHandle | None = None
        self._pending_messages: deque[str] = deque()
        self._send_queue_task: asyncio.Task | None = None

        # Palette manager for command palettes and dialogs
        self.palette_manager = PaletteManager(
            layout=self.layout,
            state=self.state,
            client=self._client,
            settings=self._settings,
            invalidate=self.invalidate,
        )

    def _on_settings_changed(self, name: str, _old: Any, _new: Any) -> None:
        """Handle settings changes."""
        if name in ("provider", "model") or name.startswith("api_keys."):
            self.state.provider_name = self._settings.provider
            self.state.model_name = self._settings.model
            self._client = _create_client(self._settings, self._sandbox_dir)
            self.palette_manager.client = self._client
            self.invalidate()
            return
        if name == "show_scrollbar":
            self.state.show_scrollbar = self._settings.show_scrollbar
            self.invalidate()
            return
        if name == "queue_inputs":
            self.state.queue_inputs = self._settings.queue_inputs
            self.invalidate()
            return
        if name == "theme" and self._app:
            self._app.style = get_style(self._settings.theme)
            self.layout.renderer.set_theme(self._settings.theme)
            self.invalidate()

    def _create_application(self) -> Application:
        """Create the prompt_toolkit Application."""
        app = Application(
            layout=self.layout.create_layout(),
            key_bindings=create_keybindings(self),
            style=get_style(self._settings.theme),
            full_screen=True,
            mouse_support=True,
        )
        app.ttimeoutlen = 0.01  # Reduce escape key delay (default 0.5s)

        # Wrap output in synchronized update sequences (DEC mode 2026).
        # The terminal buffers all writes between begin/end markers and
        # displays them atomically, eliminating tearing on scroll/redraw.
        synced = SynchronizedOutput(app.output)
        app.output = synced
        app.renderer.output = synced

        return app

    async def _run_spinner(self) -> None:
        """Periodically refresh UI to animate the spinner."""
        while True:
            await asyncio.sleep(0.1)
            self.invalidate()

    def _start_spinner(self) -> None:
        """Start the spinner animation task."""
        if self._spinner_task is None:
            self._spinner_task = asyncio.create_task(self._run_spinner())

    async def _stop_spinner(self) -> None:
        """Stop the spinner animation task."""
        if self._spinner_task:
            self._spinner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._spinner_task
            self._spinner_task = None

    async def _process_stream(self, message: str) -> None:  # noqa: C901 - allow complex
        """Process the response stream from backend."""
        stream = self._client.chat(message)

        async for event in stream:
            if isinstance(event, TextDelta):
                await self._stop_spinner()  # Stop spinner once content arrives
                self.state.append_delta(event.text)
                self.invalidate()
            elif isinstance(event, ToolCallRequested):
                self.state.transition_to_tool(event.call)
                self.invalidate()
            elif isinstance(event, ProviderToolStarted):
                call = ToolCall(tool_name=event.tool_name, call_id=event.call_id, arguments={})
                self.state.transition_to_tool(call)
                self.invalidate()
            elif isinstance(event, ToolCallResult):
                display = event.result.output.display
                self.state.complete_tool_message(
                    event.result.call_id,
                    display,
                    is_error=event.result.output.is_error,
                )
                self.invalidate()
            elif isinstance(event, ProviderToolCompleted):
                self.state.complete_tool_message(
                    event.call_id,
                    event.display,
                    is_error=event.is_error,
                )
                self.invalidate()

    def _cancel_exit_reset(self) -> None:
        if self._exit_reset_handle:
            self._exit_reset_handle.cancel()
            self._exit_reset_handle = None

    def _reset_exit_request(self) -> None:
        self.state.reset_exit_request()
        self._exit_reset_handle = None
        self.invalidate()

    def request_exit(self, timeout_seconds: float = 3.0) -> bool:
        """Request application exit. Returns True if should exit immediately."""
        if self.state.exit_requested:
            self._cancel_exit_reset()
            return True

        self.state.request_exit()
        self._cancel_exit_reset()
        if self._app:
            loop = asyncio.get_running_loop()
            self._exit_reset_handle = loop.call_later(timeout_seconds, self._reset_exit_request)
        return False

    def invalidate(self) -> None:
        """Trigger a UI refresh."""
        if self._app:
            self._app.invalidate()

    def _kick_send_queue(self) -> None:
        if self._send_queue_task and not self._send_queue_task.done():
            return
        self._send_queue_task = asyncio.create_task(self._drain_send_queue())

    async def _drain_send_queue(self) -> None:
        while self._pending_messages and not self.state.is_streaming:
            next_message = self._pending_messages.popleft()
            if self.state.pending_inputs:
                self.state.pending_inputs.pop(0)
            self.invalidate()
            await self.send_message(next_message)

    def enqueue_message(self, text: str, *, cancel_current: bool = False) -> None:
        """Queue a message to be sent after the current stream completes."""
        if not text or not text.strip():
            return
        cleaned = text.strip()
        self._pending_messages.append(cleaned)
        self.state.pending_inputs.append(cleaned)
        self.invalidate()
        if cancel_current and self.state.is_streaming:
            self.cancel_streaming()
        if not self.state.is_streaming:
            self._kick_send_queue()

    def dequeue_all(self) -> None:
        """Remove all queued messages."""
        if not self._pending_messages:
            return
        self._pending_messages.clear()
        self.state.pending_inputs.clear()
        self.invalidate()

    async def send_message(self, text: str) -> None:
        """Send a message and process the response stream."""
        self.state.begin_response(text)
        self._start_spinner()
        self.invalidate()

        try:
            self._streaming_task = asyncio.create_task(self._process_stream(text))
            await self._streaming_task
        except asyncio.CancelledError:
            pass
        except ProviderAuthenticationError:
            provider = self._settings.provider
            error_msg = (
                f"\n\n**Authentication failed for {provider.title()}.**\n\n"
                f"Please check your API key. Press `Ctrl+P` → `Connect Provider` to update it."
            )
            self.state.append_delta(error_msg)
        except Exception as e:
            error_msg = f"\n\n**Error:** {type(e).__name__}: {e}"
            self.state.append_delta(error_msg)
        finally:
            await self._stop_spinner()
            self.state.end_response()
            self._streaming_task = None
            self.invalidate()
            self._kick_send_queue()

    def cancel_streaming(self) -> None:
        """Cancel the current streaming operation."""
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        self.palette_manager.set_app(self._app)
        await self._app.run_async()
