from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import (
    ConditionalKeyBindings,
    KeyBindings,
    KeyBindingsBase,
    KeyPressEvent,
    merge_key_bindings,
)
from prompt_toolkit.keys import Keys

from koda_tui.terminal.keys import ALT_DOWN, ALT_UP, COMMAND_DOWN, COMMAND_UP

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.app.application import KodaTuiApp


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


def _cancelable(app: KodaTuiApp) -> Condition:
    """Return whether there is in-flight work to cancel."""
    return Condition(lambda: app.state.responding)


def _queue_pending(app: KodaTuiApp) -> Condition:
    """Return whether queued inputs are waiting to be sent."""
    return Condition(lambda: bool(app.state.pending_inputs))


def _create_main_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901
    """App-wide commands, whatever has focus."""
    kb = KeyBindings()

    @kb.add(*ALT_UP)
    def _edit_last_queued(_event: KeyPressEvent) -> None:
        text = app.pop_last_queued_message()
        if text is not None:
            app.screen.composer.text = text
            app.invalidate()

    @kb.add(*ALT_DOWN)
    def _ignore_alt_down(_event: KeyPressEvent) -> None:
        return None

    @kb.add(*COMMAND_UP)
    def _ignore_command_up(_event: KeyPressEvent) -> None:
        return None

    @kb.add(*COMMAND_DOWN)
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
        if app.state.responding:
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

    return kb


def _create_queue_keybindings(app: KodaTuiApp) -> KeyBindings:
    """Create key bindings active while queued inputs are present."""
    kb = KeyBindings()

    @kb.add(Keys.Escape)
    def _send_queue_now(_event: KeyPressEvent) -> None:
        app.steer_and_send_queue()

    return kb


def create_keybindings(app: KodaTuiApp) -> KeyBindingsBase:
    """Create key bindings for the TUI."""

    return merge_key_bindings(
        [
            _create_main_keybindings(app),
            ConditionalKeyBindings(
                _create_queue_keybindings(app),
                filter=_queue_pending(app),
            ),
        ]
    )
