from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from prompt_toolkit import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.output import ColorDepth

from koda_tui.app.keybindings import create_keybindings
from koda_tui.appearance import Appearance
from koda_tui.messaging import Conversation, Outbox
from koda_tui.palette.context import PaletteContext
from koda_tui.palette.palette import CommandPalette
from koda_tui.state import AppState
from koda_tui.terminal import Terminal, keys
from koda_tui.views import Screen

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import BaseStyle

    from koda_common.settings import SettingChange
    from koda_service import KodaService
    from koda_tui.appearance import RGBColor
    from koda_tui.settings import AppSettings


EXIT_TIMEOUT = 3.0  # Seconds a second Ctrl+C has to come within to exit.


class FullScreenApplication(Application[None]):
    """Koda's full-screen prompt_toolkit Application, showing ``screen``."""

    def __init__(
        self,
        screen: Screen,
        *,
        key_bindings: KeyBindings,
        style: BaseStyle,
        terminal: Terminal,
    ) -> None:
        keys.register()
        super().__init__(
            layout=screen.layout,
            key_bindings=key_bindings,
            style=style,
            full_screen=True,
            color_depth=ColorDepth.TRUE_COLOR,
            mouse_support=True,
            input=terminal.input(),
        )
        self.ttimeoutlen = 0.01  # Raw terminal Esc sequence timeout.
        self.timeoutlen = 0.05  # Key-binding prefix timeout, e.g. Esc before Alt chords.
        self.after_render += terminal.after_render

    def _on_resize(self) -> None:
        """Handle terminal resize events without flashing a blank frame."""
        if self.full_screen:
            # prompt_toolkit's default full-screen path calls renderer.erase(),
            # which flushes a visible blank frame on every resize signal.
            # This prevents screen flickering on resize.
            self.invalidate()
            return
        super()._on_resize()


class ExitPrompt:
    """Asks for a second Ctrl+C before exiting, through ``state.exit_requested``,
    until ``EXIT_TIMEOUT`` runs out."""

    def __init__(self, state: AppState, *, invalidate: Callable[[], None]) -> None:
        self._state = state
        self._invalidate = invalidate
        self._dismissals = 0  # A timeout only dismisses the ask it was started for.

    def confirm(self) -> bool:
        """Whether this Ctrl+C confirms the exit; the first press only asks."""
        if self._state.exit_requested:
            self.dismiss()
            return True
        self._state.exit_requested = True
        dismissals = self._dismissals
        with suppress(RuntimeError):  # Without a running loop, it asks until dismissed.
            asyncio.get_running_loop().call_later(EXIT_TIMEOUT, self._expire, dismissals)
        self._invalidate()
        return False

    def dismiss(self) -> None:
        """Stop asking for a second Ctrl+C."""
        self._dismissals += 1
        if self._state.exit_requested:
            self._state.exit_requested = False
            self._invalidate()

    def _expire(self, dismissals: int) -> None:
        if dismissals == self._dismissals:
            self.dismiss()


class KodaTuiApp:
    """Main TUI application."""

    def __init__(self, app_settings: AppSettings, service: KodaService, workspace: Path) -> None:
        self.app_settings = app_settings
        self._service = service
        self._app: FullScreenApplication | None = None  # Created on run.
        self._terminal = Terminal(on_background=self.on_terminal_background)

        self.state = AppState.load(workspace, service, app_settings.core)
        self.exit_prompt = ExitPrompt(self.state, invalidate=self.invalidate)
        self.appearance = Appearance(app_settings.tui.theme)
        self.screen = Screen(
            self.state,
            on_submit=self.submit,
            show_scrollbar=Condition(lambda: app_settings.tui.show_scrollbar),
        )

        conversation = Conversation(self.state)
        self.outbox = Outbox(
            state=self.state,
            conversation=conversation,
            service=service,
            invalidate=self.invalidate,
        )
        self._palette = CommandPalette(
            PaletteContext(
                overlays=self.screen.overlays,
                service=service,
                settings=app_settings,
                state=self.state,
                conversation=conversation,
                outbox=self.outbox,
                terminal=self._terminal,
            ),
        )

    async def run(self) -> None:
        """Start the TUI application, following settings changes while it runs."""
        unsubscribe_core = self.app_settings.core.subscribe(self.on_settings_changed)
        unsubscribe_tui = self.app_settings.tui.subscribe(self.on_tui_settings_changed)
        self._app = FullScreenApplication(
            self.screen,
            key_bindings=create_keybindings(self),
            style=self.appearance.style,
            terminal=self._terminal,
        )
        try:
            await self._app.run_async()
        finally:
            self._terminal.close()  # In case the final render failed before turning it off.
            unsubscribe_core()
            unsubscribe_tui()

    def invalidate(self) -> None:
        """Trigger a UI refresh."""
        if self._app:
            self._app.invalidate()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    def cycle_thinking(self) -> None:
        """Move to the active model's next thinking level, wrapping around."""
        thinking = self.state.next_thinking()
        if thinking is not None:
            self.app_settings.core.set("thinking", thinking)

    def toggle_palette(self) -> None:
        """Open the command palette, or close it and any dialogs it opened."""
        if self.screen.overlays.is_open:
            self.screen.overlays.close_all()
        else:
            self._palette.open()

    def submit(self, text: str, *, alternate: bool) -> None:
        """While Koda responds, Enter queues and Alt+Enter steers, or the other way
        round when the input mode prefers steering. Writing a message takes back a
        press of Ctrl+C."""
        self.exit_prompt.dismiss()
        self.outbox.submit(text, steer=alternate == self.app_settings.tui.queue_inputs)

    def on_settings_changed(self, _changes: tuple[SettingChange, ...]) -> None:
        """Pass the settings on to the service, which rebuilds its agent when next
        asked, and show what they change."""
        self._service.update_settings(self.app_settings.core)
        self.state.refresh(self._service, self.app_settings.core)
        self.invalidate()

    def on_tui_settings_changed(self, changes: tuple[SettingChange, ...]) -> None:
        """Apply a new theme, and redraw for any change."""
        if any(change.name == "theme" for change in changes):
            self.appearance.theme = self.app_settings.tui.theme
        self.invalidate()

    def on_terminal_background(self, background: RGBColor) -> None:
        self.appearance.terminal_background = background
        self.invalidate()
