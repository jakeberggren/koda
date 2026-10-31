from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app_session
from prompt_toolkit.input.vt100 import Vt100Input
from prompt_toolkit.layout import Layout
from prompt_toolkit.output import ColorDepth, Output

from koda.llm import ThinkingOption
from koda_tui.app.input import OSC11_QUERY, KodaVt100Input, parse_osc11
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.queue import MessageQueue
from koda_tui.app.streaming import StreamProcessor
from koda_tui.appearance import Appearance
from koda_tui.palette.context import PaletteContext
from koda_tui.palette.root import RootMenu
from koda_tui.state import AppState
from koda_tui.ui.overlays import Overlays
from koda_tui.views import Screen

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_toolkit.input import Input

    from koda_common.settings import SettingChange
    from koda_service import KodaService
    from koda_tui.settings import AppSettings


_FOCUS_REPORTING_ENABLE = "\033[?1004h"
_FOCUS_REPORTING_DISABLE = "\033[?1004l"


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
        app_settings: AppSettings,
        service: KodaService,
        workspace_root: Path,
    ) -> None:
        self._app_settings = app_settings
        self._service = service
        self._workspace_root = workspace_root

        # Subscribe to settings changes
        self._unsubscribe_settings = self._app_settings.core.subscribe(self._on_settings_changed)
        self._unsubscribe_tui_settings = self._app_settings.tui.subscribe(
            self._on_tui_settings_changed
        )
        self._closed = False

        self.appearance = Appearance(self._app_settings.tui.theme)

        # Initialize state
        self.state = AppState(
            workspace_root=self._workspace_root,
            provider_id=self._app_settings.core.provider,
            service_status=self._service.status(),
            thinking=ThinkingOption.none(),
            context_window=None,
            thinking_supported=False,
            show_scrollbar=self._app_settings.tui.show_scrollbar,
            queue_inputs=self._app_settings.tui.queue_inputs,
        )

        self.screen = Screen(self.state)

        # Application instance (created on run)
        self._app: Application[None] | None = None
        self._terminal_input: Input | None = None
        self._terminal_output: Output | None = None
        self._exit_reset_handle: asyncio.TimerHandle | None = None
        self._focus_reporting_enabled = False

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
        self.overlays = Overlays(self.screen.root, fallback=self.screen.composer.buffer)
        self._palette = RootMenu(
            PaletteContext(
                overlays=self.overlays,
                service=self._service,
                settings=self._app_settings,
                state=self.state,
                cancel_streaming=self.cancel_streaming,
                refresh_theme=self.refresh_theme,
            ),
        )
        self._refresh_service_state()

    def _write_control_sequence(self, data: str) -> None:
        if self._terminal_output:
            self._terminal_output.write_raw(data)
            self._terminal_output.flush()

    @staticmethod
    def _wrap_terminal_input(terminal_input: Input) -> Input:
        if isinstance(terminal_input, Vt100Input):
            return KodaVt100Input(terminal_input.stdin)
        return terminal_input

    def _create_application(self) -> Application[None]:
        """Create the prompt_toolkit Application."""
        app_session = get_app_session()
        self._terminal_input = self._wrap_terminal_input(app_session.input)
        self._terminal_output = app_session.output

        app = _KodaApplication(
            layout=Layout(self.screen, focused_element=self.screen.composer.buffer),
            key_bindings=create_keybindings(self),
            style=self.appearance.style,
            full_screen=True,
            color_depth=ColorDepth.TRUE_COLOR,
            mouse_support=True,
            input=self._terminal_input,
        )
        app.ttimeoutlen = 0.01  # Raw terminal Esc sequence timeout.
        app.timeoutlen = 0.05  # Key-binding prefix timeout, e.g. Esc before Alt chords.
        app.after_render += self._sync_focus_reporting
        app.after_render += self._request_initial_terminal_background_refresh

        return app

    def _sync_focus_reporting(self, app: Application[None]) -> None:
        """Toggle terminal focus reporting only while the terminal is in raw mode.

        Renders happen inside prompt_toolkit's ``raw_mode()`` context, including the
        final "done" render. Enabling here (instead of before ``run_async``) ensures the
        terminal's immediate ``ESC[I`` focus report is not echoed by the cooked-mode tty
        onto the main screen, and disabling on the final render ensures no focus events
        leak to the shell after exit.
        """
        if app.is_done:
            if self._focus_reporting_enabled:
                self._write_control_sequence(_FOCUS_REPORTING_DISABLE)
                self._focus_reporting_enabled = False
        elif not self._focus_reporting_enabled:
            self._write_control_sequence(_FOCUS_REPORTING_ENABLE)
            self._focus_reporting_enabled = True

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
        ) or any(name.startswith("credentials.") for name in change_names)

    def _apply_service_setting_changes(self, change_names: set[str]) -> bool:
        if not self._has_service_change(change_names):
            return False
        self._service.update_settings(self._app_settings.core)
        self._refresh_service_state()
        return True

    def request_terminal_background_refresh(self) -> None:
        """Ask the terminal for its background color through prompt_toolkit IO."""
        self._write_control_sequence(OSC11_QUERY)

    def _request_initial_terminal_background_refresh(self, app: Application[None]) -> None:
        app.after_render -= self._request_initial_terminal_background_refresh
        self.request_terminal_background_refresh()

    def handle_terminal_background_response(self, response: str) -> None:
        """Store an OSC 11 background response received by prompt_toolkit."""
        terminal_background = parse_osc11(response)
        if terminal_background is None:
            return
        self.appearance.terminal_background = terminal_background
        self.invalidate()

    def refresh_theme(self) -> None:
        """Re-detect the terminal background and redraw with the current theme."""
        self.request_terminal_background_refresh()
        self.invalidate()

    def handle_terminal_focus_in(self) -> None:
        """Re-detect the terminal background, which may have changed while unfocused."""
        self.request_terminal_background_refresh()

    def _apply_ui_setting_changes(self, change_names: set[str]) -> bool:
        should_invalidate = False
        if "show_scrollbar" in change_names:
            self.state.show_scrollbar = self._app_settings.tui.show_scrollbar
            self.screen.chat.clear_caches()
            should_invalidate = True
        if "queue_inputs" in change_names:
            self.state.queue_inputs = self._app_settings.tui.queue_inputs
            should_invalidate = True
        if "theme" in change_names:
            self.appearance.theme = self._app_settings.tui.theme
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

    def _on_tui_settings_changed(self, changes: tuple[SettingChange, ...]) -> None:
        """Handle committed TUI-only settings changes."""
        change_names = {change.name for change in changes}
        if self._apply_ui_setting_changes(change_names):
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
    def app_settings(self) -> AppSettings:
        return self._app_settings

    @property
    def service(self) -> KodaService:
        return self._service

    def _refresh_service_state(self) -> None:
        self.state.provider_id = self._app_settings.core.provider
        self.state.service_status = self._service.status()
        self.state.warnings = self._service.diagnostics().startup_warnings
        self.state.configured_providers = self._service.list_configured_providers()

        self.state.active_model = None
        if (
            self.state.service_status.is_ready
            and self._app_settings.core.provider is not None
            and self._app_settings.core.model is not None
        ):
            self.state.active_model = self._service.get_model(
                self._app_settings.core.provider,
                self._app_settings.core.model,
            )

        self.state.thinking = (
            self.state.active_model.resolve_thinking_option(self._app_settings.core.thinking)
            if self.state.active_model is not None
            else ThinkingOption.none()
        )
        self.state.context_window = (
            self.state.active_model.context_window if self.state.active_model else None
        )
        self.state.thinking_supported = (
            self.state.active_model.supports_thinking
            if self.state.active_model is not None
            else False
        )

    def enqueue_message(self, text: str) -> None:
        """Queue a message to be sent after the current stream completes."""
        self._message_queue.enqueue(text)

    def steer_message(self, text: str) -> None:
        """Steer the current stream and send a message as soon as possible."""
        self._message_queue.steer(text)

    def dequeue_all(self) -> None:
        """Remove all queued messages."""
        self._message_queue.dequeue_all()

    def pop_last_queued_message(self) -> str | None:
        """Remove and return the most recently queued message."""
        return self._message_queue.pop_last()

    def steer_and_send_queue(self) -> None:
        """Steer the current stream and send queued messages as soon as possible."""
        self._message_queue.steer_and_drain()

    async def send_message(self, text: str) -> None:
        """Send a message and process the response stream."""
        await self._stream_processor.stream(text, self._service)
        self._message_queue.kick()

    def cancel_streaming(self) -> None:
        """Cancel the current streaming operation."""
        self._stream_processor.cancel_stream()

    def toggle_palette(self) -> None:
        """Open the command palette, or close it and any dialogs it opened."""
        if self.overlays.is_open:
            self.overlays.close_all()
        else:
            self._palette.open()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    def close(self) -> None:
        """Release app resources and subscriptions."""
        if self._closed:
            return
        self._closed = True
        if self._terminal_output:
            # Fallback in case the final render failed before disabling it.
            if self._focus_reporting_enabled:
                self._write_control_sequence(_FOCUS_REPORTING_DISABLE)
                self._focus_reporting_enabled = False
            self._terminal_output = None
        self._terminal_input = None
        self._unsubscribe_settings()
        self._unsubscribe_tui_settings()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        try:
            await self._app.run_async()
        finally:
            self.close()
