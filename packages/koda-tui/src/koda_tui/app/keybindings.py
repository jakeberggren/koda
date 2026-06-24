from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import (
    ConditionalKeyBindings,
    KeyBindings,
    KeyBindingsBase,
    KeyPressEvent,
    merge_key_bindings,
)
from prompt_toolkit.keys import Keys

from koda_tui.app.input import FOCUS_IN_KEY, FOCUS_OUT_KEY, OSC11_RESPONSE_KEY

ALT_ENTER_KEY = (Keys.Escape, Keys.Enter)
ALT_UP_KEY = (Keys.Escape, Keys.Up)
ALT_DOWN_KEY = (Keys.Escape, Keys.Down)
COMMAND_UP_KEY = (Keys.Escape, Keys.Escape, Keys.Up)
COMMAND_DOWN_KEY = (Keys.Escape, Keys.Escape, Keys.Down)

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.app.application import KodaTuiApp

_CTRL_LETTER_KEYS = {
    "a": Keys.ControlA,
    "b": Keys.ControlB,
    "c": Keys.ControlC,
    "d": Keys.ControlD,
    "e": Keys.ControlE,
    "f": Keys.ControlF,
    "g": Keys.ControlG,
    "h": Keys.ControlH,
    "i": Keys.ControlI,
    "j": Keys.ControlJ,
    "k": Keys.ControlK,
    "l": Keys.ControlL,
    "m": Keys.ControlM,
    "n": Keys.ControlN,
    "o": Keys.ControlO,
    "p": Keys.ControlP,
    "q": Keys.ControlQ,
    "r": Keys.ControlR,
    "s": Keys.ControlS,
    "t": Keys.ControlT,
    "u": Keys.ControlU,
    "v": Keys.ControlV,
    "w": Keys.ControlW,
    "x": Keys.ControlX,
    "y": Keys.ControlY,
    "z": Keys.ControlZ,
}


def _register_terminal_sequences() -> None:
    """Register terminal-specific escape sequences for modified keys."""
    # Ctrl+letter keys - kitty keyboard protocol / CSI u.
    for letter, key in _CTRL_LETTER_KEYS.items():
        ANSI_SEQUENCES[f"\x1b[{ord(letter)};5u"] = key

    # Escape - kitty keyboard protocol / CSI u.
    ANSI_SEQUENCES["\x1b[27u"] = Keys.Escape
    ANSI_SEQUENCES["\x1b[27;1u"] = Keys.Escape

    # Word delete / modified Backspace.
    ANSI_SEQUENCES["\x1b\x7f"] = Keys.ControlW
    ANSI_SEQUENCES["\x1b\b"] = Keys.ControlW
    ANSI_SEQUENCES["\x1b[127;3u"] = Keys.ControlW
    ANSI_SEQUENCES["\x1b[8;3u"] = Keys.ControlW
    ANSI_SEQUENCES["\x1b[127;5u"] = Keys.ControlW
    ANSI_SEQUENCES["\x1b[8;5u"] = Keys.ControlW

    # Modified Enter - kitty keyboard protocol / CSI u.
    # Shift/Ctrl+Enter insert newlines; Alt+Enter is alternate submit.
    ANSI_SEQUENCES["\x1b[13;5u"] = Keys.ControlJ
    ANSI_SEQUENCES["\x1b[10;5u"] = Keys.ControlJ
    ANSI_SEQUENCES["\x1b[13;2u"] = Keys.ControlJ
    ANSI_SEQUENCES["\x1b[10;2u"] = Keys.ControlJ
    ANSI_SEQUENCES["\x1b[13;3u"] = ALT_ENTER_KEY
    ANSI_SEQUENCES["\x1b[10;3u"] = ALT_ENTER_KEY

    # Modified Enter - legacy terminal sequences.
    ANSI_SEQUENCES["\x1b[27;2;13~"] = Keys.ControlJ  # Shift+Enter - xterm

    # Alt+Enter - ESC+CR/LF (terminals that send literal escape + enter)
    ANSI_SEQUENCES["\x1b[27;3;13~"] = ALT_ENTER_KEY
    ANSI_SEQUENCES["\x1b\r"] = ALT_ENTER_KEY
    ANSI_SEQUENCES["\x1b\n"] = ALT_ENTER_KEY

    # Alt+Up/Down - common modified-arrow encodings. Do not map plain ESC+[A/B.
    ANSI_SEQUENCES["\x1b[1;3A"] = ALT_UP_KEY
    ANSI_SEQUENCES["\x1b[65;3u"] = ALT_UP_KEY
    ANSI_SEQUENCES["\x1b[1;3B"] = ALT_DOWN_KEY
    ANSI_SEQUENCES["\x1b[66;3u"] = ALT_DOWN_KEY

    # Command+Up/Down in some terminals emits CSI 1;1 A/B, which prompt_toolkit
    # does not recognize. Swallow these so they don't leak into the input buffer.
    ANSI_SEQUENCES["\x1b[1;1A"] = COMMAND_UP_KEY
    ANSI_SEQUENCES["\x1b[1;1B"] = COMMAND_DOWN_KEY


async def _submit_buffer(
    app: KodaTuiApp,
    *,
    cancel_current_if_streaming: bool,
) -> None:
    """Submit the current buffer, optionally steering the current stream."""
    text = app.layout.input_area.get_text().strip()
    if not text:
        return

    app.layout.input_area.clear()

    if app.state.is_streaming:
        if cancel_current_if_streaming:
            app.steer_message(text)
        else:
            app.enqueue_message(text)
        return

    await app.send_message(text)


def _get_cycle_thinking_options(app: KodaTuiApp) -> list[ThinkingOptionId]:
    if app.state.active_model is None:
        return []
    options = app.state.active_model.effective_thinking_options
    return [option.id for option in options]


def _handle_cycle_thinking(app: KodaTuiApp) -> None:
    """Cycle through supported thinking levels."""
    if not app.state.service_status.is_ready:
        return
    options = _get_cycle_thinking_options(app)
    if not options:
        return
    try:
        current_index = options.index(app.state.thinking.id)
    except ValueError:
        current_index = -1
    app.app_settings.core.set("thinking", options[(current_index + 1) % len(options)])
    app.invalidate()


def _file_discovery_open(app: KodaTuiApp) -> Condition:
    """Return whether file discovery bindings should be active."""
    return Condition(
        lambda: app.layout.input_area.is_file_discovery_open and not app.state.palette_open
    )


def _file_discovery_has_selection(app: KodaTuiApp) -> Condition:
    """Return whether file discovery has a selectable result."""
    return Condition(
        lambda: app.layout.input_area.has_file_discovery_selection and not app.state.palette_open
    )


def _cancelable(app: KodaTuiApp) -> Condition:
    """Return whether there is in-flight work to cancel."""
    return Condition(lambda: app.state.is_streaming)


def _queue_pending(app: KodaTuiApp) -> Condition:
    """Return whether queued inputs are waiting to be sent."""
    return Condition(lambda: bool(app.state.pending_inputs))


def _create_main_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901
    """Create key bindings for the main input area."""
    kb = KeyBindings()

    @kb.add(Keys.Enter)
    async def _submit(_event: KeyPressEvent) -> None:
        await _submit_buffer(app, cancel_current_if_streaming=not app.state.queue_inputs)

    @kb.add(*ALT_ENTER_KEY)
    async def _alternate_submit(_event: KeyPressEvent) -> None:
        await _submit_buffer(app, cancel_current_if_streaming=app.state.queue_inputs)

    @kb.add(Keys.ControlJ)
    def _newline(event: KeyPressEvent) -> None:
        event.current_buffer.insert_text("\n")

    @kb.add(*ALT_UP_KEY)
    def _edit_last_queued(_event: KeyPressEvent) -> None:
        text = app.pop_last_queued_message()
        if text is not None:
            app.layout.input_area.set_text(text)
            app.invalidate()

    @kb.add(*ALT_DOWN_KEY)
    def _ignore_alt_down(_event: KeyPressEvent) -> None:
        return None

    @kb.add(*COMMAND_UP_KEY)
    def _ignore_command_up(_event: KeyPressEvent) -> None:
        return None

    @kb.add(*COMMAND_DOWN_KEY)
    def _ignore_command_down(_event: KeyPressEvent) -> None:
        return None

    @kb.add(Keys.ControlC)
    def _request_exit(_event: KeyPressEvent) -> None:
        if app.request_exit():
            app.exit()
        else:
            app.invalidate()

    @kb.add(Keys.Escape, filter=_cancelable(app))
    def _escape(_event: KeyPressEvent) -> None:
        if app.state.is_streaming:
            app.cancel_streaming()

    @kb.add(Keys.ControlP)
    def _toggle_palette(_event: KeyPressEvent) -> None:
        app.toggle_palette()

    @kb.add(Keys.ControlK)
    def _toggle_palette_alt(_event: KeyPressEvent) -> None:
        app.toggle_palette()

    @kb.add(Keys.ControlT)
    def _cycle_thinking(_event: KeyPressEvent) -> None:
        _handle_cycle_thinking(app)

    @kb.add(FOCUS_IN_KEY, eager=True, record_in_macro=False)
    def _terminal_focus_in(_event: KeyPressEvent) -> None:
        app.handle_terminal_focus_in()

    @kb.add(FOCUS_OUT_KEY, eager=True, record_in_macro=False)
    def _terminal_focus_out(_event: KeyPressEvent) -> None:
        return None

    @kb.add(OSC11_RESPONSE_KEY, eager=True, record_in_macro=False)
    def _terminal_background_response(event: KeyPressEvent) -> None:
        app.handle_terminal_background_response(event.key_sequence[0].data)

    @kb.add(Keys.Up, eager=True, filter=has_focus(app.layout.input_area.buffer))
    def _move_up(event: KeyPressEvent) -> None:
        app.layout.input_area.move_cursor_up(event.arg)

    @kb.add(Keys.Down, eager=True, filter=has_focus(app.layout.input_area.buffer))
    def _move_down(event: KeyPressEvent) -> None:
        app.layout.input_area.move_cursor_down(event.arg)

    return kb


def _create_queue_keybindings(app: KodaTuiApp) -> KeyBindings:
    """Create key bindings active while queued inputs are present."""
    kb = KeyBindings()

    @kb.add(Keys.Escape)
    def _send_queue_now(_event: KeyPressEvent) -> None:
        app.steer_and_send_queue()

    return kb


def _create_file_discovery_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901
    """Create key bindings active while the file discovery menu is open."""
    kb = KeyBindings()

    @kb.add(Keys.Up, eager=True, filter=_file_discovery_has_selection(app))
    def _move_up(_event: KeyPressEvent) -> None:
        if app.layout.input_area.move_file_discovery_selection(-1):
            app.invalidate()

    @kb.add(Keys.Down, eager=True, filter=_file_discovery_has_selection(app))
    def _move_down(_event: KeyPressEvent) -> None:
        if app.layout.input_area.move_file_discovery_selection(1):
            app.invalidate()

    @kb.add(Keys.Enter, eager=True, filter=_file_discovery_has_selection(app))
    def _accept_enter(_event: KeyPressEvent) -> None:
        if app.layout.input_area.accept_file_discovery_selection():
            app.invalidate()

    @kb.add(Keys.Tab, eager=True, filter=_file_discovery_has_selection(app))
    def _accept_tab(_event: KeyPressEvent) -> None:
        if app.layout.input_area.accept_file_discovery_selection():
            app.invalidate()

    return kb


def create_keybindings(app: KodaTuiApp) -> KeyBindingsBase:
    """Create key bindings for the TUI."""
    _register_terminal_sequences()

    return merge_key_bindings(
        [
            _create_main_keybindings(app),
            ConditionalKeyBindings(
                _create_queue_keybindings(app),
                filter=_queue_pending(app),
            ),
            ConditionalKeyBindings(
                _create_file_discovery_keybindings(app),
                filter=_file_discovery_open(app),
            ),
        ]
    )
