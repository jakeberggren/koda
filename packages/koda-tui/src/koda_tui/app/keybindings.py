"""Key binding definitions for Koda TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

if TYPE_CHECKING:
    from koda_tui.app.application import KodaTuiApp


def create_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901 - complexity
    """Create key bindings for the TUI."""
    kb = KeyBindings()

    # Register Ghostty's modified Enter sequences
    # Ctrl+Enter (modifier 5)
    ANSI_SEQUENCES["\x1b[27;5;13~"] = Keys.ControlJ
    # Shift+Enter (modifier 2) - xterm style
    ANSI_SEQUENCES["\x1b[27;2;13~"] = Keys.ControlJ
    # Shift+Enter - kitty protocol style
    ANSI_SEQUENCES["\x1b[13;2u"] = Keys.ControlJ

    @kb.add(Keys.Enter)
    async def submit_message(event) -> None:
        """Submit message on Enter."""
        if app.state.is_streaming:
            app.cancel_streaming()
            return

        buffer = event.current_buffer
        text = buffer.text.strip()

        if text:
            buffer.reset()
            await app.send_message(text)

    @kb.add(Keys.ControlJ)  # Ctrl+Enter / Ctrl+J
    def _(event) -> None:
        """Insert newline on Ctrl+Enter."""
        event.current_buffer.insert_text("\n")

    @kb.add(Keys.Escape, Keys.Enter)
    def _(event) -> None:
        """Insert newline on Escape+Enter."""
        event.current_buffer.insert_text("\n")

    @kb.add(Keys.ControlC)
    def _(_) -> None:
        """Handle Ctrl+C - cancel current operation or request exit."""
        if app.state.is_streaming:
            app.cancel_streaming()
        elif app.state.request_exit():
            app.exit()
        else:
            app.invalidate()

    @kb.add(Keys.Escape)
    def _(_) -> None:
        if app.state.is_streaming:
            app.cancel_streaming()

    return kb
