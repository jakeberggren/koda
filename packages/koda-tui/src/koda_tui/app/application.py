from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from prompt_toolkit import Application
from prompt_toolkit.application.current import get_app_session
from prompt_toolkit.filters import Condition
from prompt_toolkit.input.vt100 import Vt100Input
from prompt_toolkit.layout import Layout
from prompt_toolkit.output import ColorDepth

from koda.llm import ThinkingOption
from koda_tui.app.keybindings import create_keybindings
from koda_tui.appearance import Appearance
from koda_tui.messaging import Conversation, Outbox
from koda_tui.palette.context import PaletteContext
from koda_tui.palette.root import RootMenu
from koda_tui.rendering import Renderer
from koda_tui.state import AppState
from koda_tui.terminal import Terminal, TerminalInput, keys
from koda_tui.ui.overlays import Overlays
from koda_tui.views import Screen

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_toolkit.input import Input

    from koda_common.settings import SettingChange
    from koda_service import KodaService
    from koda_tui.appearance import RGBColor
    from koda_tui.settings import AppSettings


EXIT_TIMEOUT = 3.0  # Seconds a second Ctrl+C has to come within to exit.


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
        workspace: Path,
    ) -> None:
        self._app_settings = app_settings
        self._service = service
        self._workspace_root = workspace

        # Subscribe to settings changes
        self._unsubscribe_settings = self._app_settings.core.subscribe(self._on_settings_changed)
        self._unsubscribe_tui_settings = self._app_settings.tui.subscribe(
            self._on_tui_settings_changed
        )
        self._closed = False

        self.appearance = Appearance(self._app_settings.tui.theme)

        # Initialize state
        self.state = AppState(
            workspace=self._workspace_root,
            service_status=self._service.status(),
        )

        self.screen = Screen(
            self.state,
            renderer=Renderer(),
            on_submit=self._submit,
            show_scrollbar=Condition(lambda: self._app_settings.tui.show_scrollbar),
        )

        # Application instance (created on run)
        self._app: Application[None] | None = None
        self._terminal = Terminal(on_background=self._on_terminal_background)
        self._exit_expiry: asyncio.TimerHandle | None = None

        self.conversation = Conversation(self.state)
        self.outbox = Outbox(
            state=self.state,
            conversation=self.conversation,
            service=self._service,
            invalidate=self.invalidate,
        )
        self.overlays = Overlays(self.screen.root, fallback=self.screen.composer.buffer)
        self._palette = RootMenu(
            PaletteContext(
                overlays=self.overlays,
                service=self._service,
                settings=self._app_settings,
                state=self.state,
                conversation=self.conversation,
                outbox=self.outbox,
                terminal=self._terminal,
            ),
        )
        self._refresh_service_state()

    def _terminal_input(self, terminal_input: Input) -> Input:
        """The session's input, reading the terminal's replies when it is a real terminal."""
        if not isinstance(terminal_input, Vt100Input):
            return terminal_input
        return TerminalInput(terminal_input.stdin, self._terminal)

    def _create_application(self) -> Application[None]:
        """Create the prompt_toolkit Application."""
        keys.register()
        app = _KodaApplication(
            layout=Layout(self.screen, focused_element=self.screen.composer.buffer),
            key_bindings=create_keybindings(self),
            style=self.appearance.style,
            full_screen=True,
            color_depth=ColorDepth.TRUE_COLOR,
            mouse_support=True,
            input=self._terminal_input(get_app_session().input),
        )
        app.ttimeoutlen = 0.01  # Raw terminal Esc sequence timeout.
        app.timeoutlen = 0.05  # Key-binding prefix timeout, e.g. Esc before Alt chords.
        app.after_render += self._terminal.after_render

        return app

    def _on_terminal_background(self, background: RGBColor) -> None:
        self.appearance.terminal_background = background
        self.invalidate()

    def _on_settings_changed(self, _changes: tuple[SettingChange, ...]) -> None:
        """Pass the settings on to the service, which rebuilds its agent when next
        asked, and show what they change."""
        self._service.update_settings(self._app_settings.core)
        self._refresh_service_state()
        self.invalidate()

    def _on_tui_settings_changed(self, changes: tuple[SettingChange, ...]) -> None:
        """Apply a new theme, and redraw for any change."""
        if any(change.name == "theme" for change in changes):
            self.appearance.theme = self._app_settings.tui.theme
        self.invalidate()

    def confirm_exit(self) -> bool:
        """Whether this Ctrl+C confirms the exit. The first press asks for a second,
        through ``state.exit_requested``, until ``EXIT_TIMEOUT`` runs out."""
        if self.state.exit_requested:
            self._dismiss_exit()
            return True
        self.state.exit_requested = True
        with suppress(RuntimeError):  # Without a running app, it asks until dismissed.
            loop = asyncio.get_running_loop()
            self._exit_expiry = loop.call_later(EXIT_TIMEOUT, self._dismiss_exit)
        self.invalidate()
        return False

    def _dismiss_exit(self) -> None:
        """Stop asking for a second Ctrl+C."""
        if self._exit_expiry is not None:
            self._exit_expiry.cancel()
            self._exit_expiry = None
        if self.state.exit_requested:
            self.state.exit_requested = False
            self.invalidate()

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

    def _submit(self, text: str, *, alternate: bool) -> None:
        """While Koda responds, Enter queues and Alt+Enter steers, or the other way
        round when the input mode prefers steering. Writing a message takes back a
        press of Ctrl+C."""
        self._dismiss_exit()
        self.outbox.submit(text, steer=alternate == self._app_settings.tui.queue_inputs)

    def cycle_thinking(self) -> None:
        """Move to the active model's next thinking level, wrapping around."""
        model = self.state.active_model
        if not self.state.service_status.is_ready or model is None:
            return
        options = [option.id for option in model.effective_thinking_options]
        if not options:
            return
        current = self.state.thinking.id
        index = options.index(current) if current in options else -1
        self._app_settings.core.set("thinking", options[(index + 1) % len(options)])

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
        self._terminal.close()  # In case the final render failed before turning it off.
        self._unsubscribe_settings()
        self._unsubscribe_tui_settings()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        try:
            await self._app.run_async()
        finally:
            self.close()
