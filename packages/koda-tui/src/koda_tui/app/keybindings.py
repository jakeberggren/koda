from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import (
    ConditionalKeyBindings,
    KeyBindings,
    KeyBindingsBase,
    KeyPressEvent,
    merge_key_bindings,
)
from prompt_toolkit.keys import Keys

from koda_tui.terminal.keys import ALT_DOWN, ALT_ENTER, ALT_UP, COMMAND_DOWN, COMMAND_UP

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.app.application import KodaTuiApp


async def _submit_buffer(
    app: KodaTuiApp,
    *,
    cancel_current_if_streaming: bool,
) -> None:
    """Submit the current buffer, optionally steering the current stream."""
    text = app.screen.composer.text.strip()
    if not text:
        return

    app.screen.composer.clear()

    if app.state.responding:
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


def _mentioning(app: KodaTuiApp) -> Condition:
    """Return whether file suggestion bindings should be active."""
    return Condition(lambda: app.screen.composer.is_mentioning and not app.overlays.is_open)


def _has_suggestion(app: KodaTuiApp) -> Condition:
    """Return whether a suggested file is selected."""
    return Condition(lambda: app.screen.composer.has_suggestion and not app.overlays.is_open)


def _cancelable(app: KodaTuiApp) -> Condition:
    """Return whether there is in-flight work to cancel."""
    return Condition(lambda: app.state.responding)


def _queue_pending(app: KodaTuiApp) -> Condition:
    """Return whether queued inputs are waiting to be sent."""
    return Condition(lambda: bool(app.state.pending_inputs))


def _create_main_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901
    """Create key bindings for the main input area."""
    kb = KeyBindings()

    @kb.add(Keys.Enter)
    async def _submit(_event: KeyPressEvent) -> None:
        await _submit_buffer(app, cancel_current_if_streaming=not app.app_settings.tui.queue_inputs)

    @kb.add(*ALT_ENTER)
    async def _alternate_submit(_event: KeyPressEvent) -> None:
        await _submit_buffer(app, cancel_current_if_streaming=app.app_settings.tui.queue_inputs)

    @kb.add(Keys.ControlJ)
    def _newline(event: KeyPressEvent) -> None:
        event.current_buffer.insert_text("\n")

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

    @kb.add(Keys.Up, eager=True, filter=has_focus(app.screen.composer.buffer))
    def _move_up(event: KeyPressEvent) -> None:
        app.screen.composer.move_cursor_up(event.arg)

    @kb.add(Keys.Down, eager=True, filter=has_focus(app.screen.composer.buffer))
    def _move_down(event: KeyPressEvent) -> None:
        app.screen.composer.move_cursor_down(event.arg)

    return kb


def _create_queue_keybindings(app: KodaTuiApp) -> KeyBindings:
    """Create key bindings active while queued inputs are present."""
    kb = KeyBindings()

    @kb.add(Keys.Escape)
    def _send_queue_now(_event: KeyPressEvent) -> None:
        app.steer_and_send_queue()

    return kb


def _create_suggestion_keybindings(app: KodaTuiApp) -> KeyBindings:  # noqa: C901
    """Create key bindings active while file suggestions are showing."""
    kb = KeyBindings()

    @kb.add(Keys.Up, eager=True, filter=_has_suggestion(app))
    def _move_up(_event: KeyPressEvent) -> None:
        app.screen.composer.move_suggestion(-1)
        app.invalidate()

    @kb.add(Keys.Down, eager=True, filter=_has_suggestion(app))
    def _move_down(_event: KeyPressEvent) -> None:
        app.screen.composer.move_suggestion(1)
        app.invalidate()

    @kb.add(Keys.Enter, eager=True, filter=_has_suggestion(app))
    def _accept_enter(_event: KeyPressEvent) -> None:
        if app.screen.composer.accept_suggestion():
            app.invalidate()

    @kb.add(Keys.Tab, eager=True, filter=_has_suggestion(app))
    def _accept_tab(_event: KeyPressEvent) -> None:
        if app.screen.composer.accept_suggestion():
            app.invalidate()

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
            ConditionalKeyBindings(
                _create_suggestion_keybindings(app),
                filter=_mentioning(app),
            ),
        ]
    )
