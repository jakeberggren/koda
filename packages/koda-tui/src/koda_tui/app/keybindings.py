"""Key binding definitions for Koda TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

if TYPE_CHECKING:
    from koda_tui.app.application import KodaTuiApp


def _register_terminal_sequences() -> None:
    """Register terminal-specific escape sequences for modified Enter keys."""
    # Ctrl+Enter (modifier 5) - ghostty
    ANSI_SEQUENCES["\x1b[27;5;13~"] = Keys.ControlJ
    # Shift+Enter (modifier 2) - xterm
    ANSI_SEQUENCES["\x1b[27;2;13~"] = Keys.ControlJ
    # Shift+Enter - kitty protocol
    ANSI_SEQUENCES["\x1b[13;2u"] = Keys.ControlJ


async def _handle_enter(app: KodaTuiApp, event: KeyPressEvent) -> None:
    """Submit message on Enter, or cancel if streaming."""
    if app.state.is_streaming:
        app.cancel_streaming()
        return

    text = event.current_buffer.text.strip()
    if text:
        event.current_buffer.reset()
        await app.send_message(text)


def _handle_newline(event: KeyPressEvent) -> None:
    """Insert a literal newline."""
    event.current_buffer.insert_text("\n")


def _handle_scroll_up(app: KodaTuiApp) -> None:
    """Scroll chat area up."""
    app.layout.chat_area.scroll_up(scroll_amount=5)
    app.invalidate()


def _handle_scroll_down(app: KodaTuiApp) -> None:
    """Scroll chat area down."""
    app.layout.chat_area.scroll_down(scroll_amount=5)
    app.invalidate()


def _handle_cancel_or_exit(app: KodaTuiApp) -> None:
    """Cancel streaming, or request exit if idle."""
    if app.state.is_streaming:
        app.cancel_streaming()
    elif app.state.request_exit():
        app.exit()
    else:
        app.invalidate()


def _handle_escape(app: KodaTuiApp) -> None:
    """Cancel streaming on Escape."""
    if app.state.is_streaming:
        app.cancel_streaming()


def _handle_palette_toggle(app: KodaTuiApp) -> None:
    """Toggle command palette visibility."""
    app.toggle_palette()


def create_keybindings(app: KodaTuiApp) -> KeyBindings:
    """Create key bindings for the TUI."""
    kb = KeyBindings()
    _register_terminal_sequences()

    kb.add(Keys.Enter)(lambda event: _handle_enter(app, event))
    kb.add(Keys.ControlJ)(_handle_newline)
    kb.add(Keys.Escape, Keys.Enter)(_handle_newline)
    kb.add(Keys.Up)(lambda _: _handle_scroll_up(app))
    kb.add(Keys.Down)(lambda _: _handle_scroll_down(app))
    kb.add(Keys.ControlC)(lambda _: _handle_cancel_or_exit(app))
    kb.add(Keys.Escape)(lambda _: _handle_escape(app))
    kb.add(Keys.ControlP)(lambda _: _handle_palette_toggle(app))

    return kb
