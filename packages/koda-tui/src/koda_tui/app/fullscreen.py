"""The prompt_toolkit Application Koda runs in."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit import Application
from prompt_toolkit.output import ColorDepth

from koda_tui.terminal import keys

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import BaseStyle

    from koda_tui.terminal import Terminal
    from koda_tui.views import Screen


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
