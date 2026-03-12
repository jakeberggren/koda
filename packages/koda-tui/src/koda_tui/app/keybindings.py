from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from koda_common.contracts import ThinkingLevel

if TYPE_CHECKING:
    from koda_common.contracts import KodaBackend
    from koda_common.settings import SettingsManager
    from koda_tui.app.application import KodaTuiApp


def _register_terminal_sequences() -> None:
    """Register terminal-specific escape sequences for modified Enter keys."""
    # Ctrl+Enter (modifier 5) - ghostty
    ANSI_SEQUENCES["\x1b[27;5;13~"] = Keys.ControlJ
    # Shift+Enter (modifier 2) - xterm
    ANSI_SEQUENCES["\x1b[27;2;13~"] = Keys.ControlJ
    # Shift+Enter - kitty protocol
    ANSI_SEQUENCES["\x1b[13;2u"] = Keys.ControlJ
    # Shift+Enter - ESC+CR (terminals that send literal escape + enter)
    ANSI_SEQUENCES["\x1b\r"] = Keys.ControlJ


async def _handle_enter(app: KodaTuiApp, event: KeyPressEvent) -> None:
    """Submit message on Enter, or queue if streaming."""
    text = event.current_buffer.text.strip()
    if not text:
        return

    event.current_buffer.reset()  # clear input buffer

    if app.state.is_streaming:
        cancel_current = not app.state.queue_inputs
        app.enqueue_message(text, cancel_current=cancel_current)
        return

    await app.send_message(text)


def _handle_newline(event: KeyPressEvent) -> None:
    """Insert a literal newline."""
    event.current_buffer.insert_text("\n")


def _handle_cancel_or_exit(app: KodaTuiApp) -> None:
    """Cancel streaming, or request exit if idle."""
    if app.state.is_streaming:
        app.cancel_streaming()
    elif app.request_exit():
        app.exit()
    else:
        app.invalidate()


def _handle_escape(app: KodaTuiApp) -> None:
    """Clear queue on Escape, or cancel streaming if queue is empty."""
    if app.state.pending_inputs:
        app.dequeue_all()
        return
    if app.state.is_streaming:
        app.cancel_streaming()


def _handle_palette_toggle(app: KodaTuiApp) -> None:
    """Toggle command palette visibility."""
    app.toggle_palette()


def _get_cycle_thinking_levels(
    backend: KodaBackend,
    settings: SettingsManager,
) -> list[ThinkingLevel]:
    active_model = next(
        (
            model
            for model in backend.list_models(settings.provider)
            if model.provider == settings.provider and model.id == settings.model
        ),
        None,
    )
    if active_model is None:
        return [ThinkingLevel.NONE]

    thinking_order = [
        ThinkingLevel.NONE,
        ThinkingLevel.MINIMAL,
        ThinkingLevel.LOW,
        ThinkingLevel.MEDIUM,
        ThinkingLevel.HIGH,
        ThinkingLevel.XHIGH,
    ]
    supported = set(active_model.thinking)
    return [level for level in thinking_order if level in supported]


def _handle_cycle_thinking(app: KodaTuiApp) -> None:
    """Cycle through supported thinking levels."""
    levels = _get_cycle_thinking_levels(app.backend, app.settings)
    result = app.cycle_thinking(levels)
    if result.ok:
        app.invalidate()


def create_keybindings(app: KodaTuiApp) -> KeyBindings:
    """Create key bindings for the TUI."""
    kb = KeyBindings()
    _register_terminal_sequences()

    kb.add(Keys.Enter)(lambda event: _handle_enter(app, event))
    kb.add(Keys.ControlJ)(_handle_newline)
    kb.add(Keys.ControlC)(lambda _: _handle_cancel_or_exit(app))
    kb.add(Keys.Escape)(lambda _: _handle_escape(app))
    kb.add(Keys.ControlP)(lambda _: _handle_palette_toggle(app))
    kb.add(Keys.ControlT)(lambda _: _handle_cycle_thinking(app))

    return kb
