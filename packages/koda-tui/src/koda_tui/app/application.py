from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prompt_toolkit import Application

from koda_tui import actions
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.output import SynchronizedOutput
from koda_tui.app.queue import MessageQueue
from koda_tui.app.streaming import StreamProcessor
from koda_tui.state import AppState
from koda_tui.ui.layout import TUILayout
from koda_tui.ui.palette import PaletteManager
from koda_tui.ui.styles import get_style
from koda_tui.utils.model_selection import find_model, resolve_thinking_option, supports_thinking

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings import SettingChange, SettingsManager
    from koda_service import KodaService
    from koda_service.types import ThinkingOptionId


class _KodaApplication(Application):
    """Prompt toolkit Application subclass with updated resize behavior for KODA-TUI."""

    def _on_resize(self) -> None:
        """Handle terminal resize events without flashing a blank frame."""
        if self.full_screen:
            # prompt_toolkit's default full-screen path calls renderer.erase(),
            # which flushes a visible blank frame on every resize signal.
            # This prevents screen flickering on resize.
            self.invalidate()
            return
        super()._on_resize()


class KodaTuiApp:
    """Main TUI application."""

    def __init__(
        self,
        settings: SettingsManager,
        service: KodaService,
        workspace_root: Path,
    ) -> None:
        self._settings = settings
        self._service = service
        self._workspace_root = workspace_root

        # Subscribe to settings changes
        self._unsubscribe = self._settings.subscribe(self._on_settings_changed)
        self._closed = False

        # Initialize state
        service_status = self._service.ready()
        self.state = AppState(
            workspace_root=self._workspace_root,
            provider_name=self._settings.provider,
            model_name=self._settings.model,
            service_status=service_status,
            thinking=resolve_thinking_option(None, self._settings.thinking),
            context_window=None,
            thinking_supported=False,
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
            service=self._service,
            invalidate=self.invalidate,
            cancel_streaming=self.cancel_streaming,
        )
        self._refresh_service_state()

    def _create_application(self) -> Application:
        """Create the prompt_toolkit Application."""
        app = _KodaApplication(
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

    @staticmethod
    def _has_service_change(change_names: set[str]) -> bool:
        return bool(
            {
                "provider",
                "model",
                "thinking",
                "allow_web_search",
                "allow_extended_prompt_retention",
            }
            & change_names
        ) or any(name.startswith("api_keys.") for name in change_names)

    def _apply_service_setting_changes(self, change_names: set[str]) -> bool:
        if not self._has_service_change(change_names):
            return False
        self._service.update_settings(self._settings)
        self._refresh_service_state()
        return True

    def _apply_ui_setting_changes(self, change_names: set[str]) -> bool:
        should_invalidate = False
        if "show_scrollbar" in change_names:
            self.state.show_scrollbar = self._settings.show_scrollbar
            should_invalidate = True
        if "queue_inputs" in change_names:
            self.state.queue_inputs = self._settings.queue_inputs
            should_invalidate = True
        if "theme" in change_names and self._app:
            self._app.style = get_style(self._settings.theme)
            self.layout.renderer.set_theme(self._settings.theme)
            should_invalidate = True
        return should_invalidate

    def _on_settings_changed(self, changes: tuple[SettingChange, ...]) -> None:
        """Handle committed settings changes."""
        change_names = {change.name for change in changes}
        should_invalidate = self._apply_service_setting_changes(change_names)
        if self._apply_ui_setting_changes(change_names):
            should_invalidate = True
        if should_invalidate:
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

    @property
    def settings(self) -> SettingsManager:
        return self._settings

    @property
    def service(self) -> KodaService:
        return self._service

    def _refresh_service_state(self) -> None:
        self.state.provider_name = self._settings.provider
        self.state.model_name = self._settings.model
        self.state.service_status = self._service.ready()

        active_model = None
        if (
            self.state.service_status.is_ready
            and self._settings.provider is not None
            and self._settings.model is not None
        ):
            active_model = find_model(
                self._service.list_models(self._settings.provider),
                provider=self._settings.provider,
                model_id=self._settings.model,
            )

        self.state.thinking = resolve_thinking_option(active_model, self._settings.thinking)
        self.state.context_window = active_model.context_window if active_model else None
        self.state.thinking_supported = supports_thinking(active_model)

    def enqueue_message(self, text: str, *, cancel_current: bool = False) -> None:
        """Queue a message to be sent after the current stream completes."""
        self._message_queue.enqueue(text, cancel_current=cancel_current)

    def dequeue_all(self) -> None:
        """Remove all queued messages."""
        self._message_queue.dequeue_all()

    async def send_message(self, text: str) -> None:
        """Send a message and process the response stream."""
        await self._stream_processor.stream(text, self._service)
        self._message_queue.kick()

    def cancel_streaming(self) -> None:
        """Cancel the current streaming operation."""
        self._stream_processor.cancel_stream()

    def cycle_thinking(self, options: list[ThinkingOptionId]):
        return actions.cycle_thinking(options, self._settings)

    def toggle_palette(self) -> None:
        """Toggle command palette visibility."""
        self._palette_manager.toggle()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    def close(self) -> None:
        """Release app resources and subscriptions."""
        if self._closed:
            return
        self._closed = True
        self._unsubscribe()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        self._palette_manager.set_app(self._app)
        try:
            await self._app.run_async()
        finally:
            self.close()
