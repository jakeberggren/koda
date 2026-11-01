from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from koda_tui.terminal.keys import ALT_DOWN, ALT_UP, COMMAND_DOWN, COMMAND_UP

if TYPE_CHECKING:
    from koda_tui.app.application import KodaTuiApp


def create_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901 - one handler per key
    """App-wide commands, whatever has focus."""
    kb = KeyBindings()
    state = app.state

    @kb.add(*ALT_UP)
    def _edit_last_queued(_event: KeyPressEvent) -> None:
        text = app.outbox.take_last()
        if text is not None:
            app.screen.composer.text = text
            app.invalidate()

    @kb.add(*ALT_DOWN)
    @kb.add(*COMMAND_UP)
    @kb.add(*COMMAND_DOWN)
    def _ignore(_event: KeyPressEvent) -> None:
        """Keys bound only so they don't type their escape sequence as text."""

    @kb.add(Keys.ControlC)
    def _exit(_event: KeyPressEvent) -> None:
        if app.exit_prompt.confirm():
            app.exit()

    @kb.add(Keys.Escape, filter=Condition(lambda: state.responding or bool(state.pending_inputs)))
    def _escape(_event: KeyPressEvent) -> None:
        """Send what's queued now, interrupting the response; with nothing queued, just
        interrupt it."""
        if state.pending_inputs:
            app.outbox.send_now()
        else:
            app.outbox.cancel()

    @kb.add(Keys.ControlP)
    @kb.add(Keys.ControlK)
    def _toggle_palette(_event: KeyPressEvent) -> None:
        app.toggle_palette()

    @kb.add(Keys.ControlT)
    def _cycle_thinking(_event: KeyPressEvent) -> None:
        app.cycle_thinking()

    return kb
