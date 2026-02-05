from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from prompt_toolkit import Application

from koda_common import SettingsManager
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.output import SynchronizedOutput
from koda_tui.app.queue import MessageQueue
from koda_tui.app.streaming import StreamProcessor
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
        self._exit_reset_handle: asyncio.TimerHandle | None = None

        self._message_queue = MessageQueue(
            state=self.state,
            send_message=self.send_message,
            invalidate=self.invalidate,
            cancel_streaming=self.cancel_streaming,
        )
        self._stream_processor = StreamProcessor(
            state=self.state,
            invalidate=self.invalidate,
        )
        self._palette_manager = PaletteManager(
            layout=self.layout,
            state=self.state,
            settings=self._settings,
            invalidate=self.invalidate,
        )

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

    def _on_settings_changed(self, name: str, _old: Any, _new: Any) -> None:
        """Handle settings changes."""
        if name in ("provider", "model") or name.startswith("api_keys."):
            self.state.provider_name = self._settings.provider
            self.state.model_name = self._settings.model
            self._client = _create_client(self._settings, self._sandbox_dir)
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

    def _on_exit_timeout(self) -> None:
        self.state.exit_requested = False
        self._exit_reset_handle = None
        self.invalidate()

    def request_exit(self, timeout_seconds: float = 3.0) -> bool:
        """Request application exit. Returns True if should exit immediately (on double-press)."""
        if self._exit_reset_handle:
            self._exit_reset_handle.cancel()
            self._exit_reset_handle = None

        if self.state.exit_requested:
            return True

        self.state.exit_requested = True
        if self._app:
            loop = asyncio.get_running_loop()
            self._exit_reset_handle = loop.call_later(timeout_seconds, self._on_exit_timeout)
        return False

    def invalidate(self) -> None:
        """Trigger a UI refresh."""
        if self._app:
            self._app.invalidate()

    def enqueue_message(self, text: str, *, cancel_current: bool = False) -> None:
        """Queue a message to be sent after the current stream completes."""
        self._message_queue.enqueue(text, cancel_current=cancel_current)

    def dequeue_all(self) -> None:
        """Remove all queued messages."""
        self._message_queue.dequeue_all()

    async def send_message(self, text: str) -> None:
        """Send a message and process the response stream."""
        await self._stream_processor.stream(text, self._client)
        self._message_queue.kick()

    def cancel_streaming(self) -> None:
        """Cancel the current streaming operation."""
        self._stream_processor.cancel_stream()

    def toggle_palette(self) -> None:
        """Toggle command palette visibility."""
        self._palette_manager.toggle(self._client)

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        self._palette_manager.set_app(self._app)
        await self._app.run_async()
