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

from koda_tui.utils.model_selection import find_model, supported_thinking_options

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager
    from koda_service import CatalogService
    from koda_service.types import ModelDefinition, ProviderDefinition, ThinkingOptionId
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


async def _submit_buffer(
    app: KodaTuiApp,
    *,
    cancel_current_if_streaming: bool,
) -> None:
    """Submit the current buffer, optionally interrupting the current stream."""
    text = app.layout.input_area.get_text().strip()
    if not text:
        return

    app.layout.input_area.clear()

    if app.state.is_streaming:
        app.enqueue_message(text, cancel_current=cancel_current_if_streaming)
        return

    await app.send_message(text)


async def _handle_enter(app: KodaTuiApp) -> None:
    """Submit message on Enter, or queue if streaming."""
    await _submit_buffer(
        app,
        cancel_current_if_streaming=not app.state.queue_inputs,
    )


def _handle_cancel_or_exit(app: KodaTuiApp) -> None:
    """Cancel streaming, or request exit if idle."""
    if app.state.is_streaming:
        app.cancel_streaming()
    elif app.request_exit():
        app.exit()
    else:
        app.invalidate()


def _handle_escape(app: KodaTuiApp) -> None:
    """Cancel streaming on Escape."""
    if app.state.is_streaming:
        app.cancel_streaming()


def _get_cycle_thinking_options(
    catalog_service: CatalogService[ProviderDefinition, ModelDefinition],
    settings: SettingsManager,
) -> list[ThinkingOptionId]:
    active_model = find_model(
        catalog_service.list_models(settings.provider),
        provider=settings.provider,
        model_id=settings.model,
    )
    return [option.id for option in supported_thinking_options(active_model)]


def _handle_cycle_thinking(app: KodaTuiApp) -> None:
    """Cycle through supported thinking levels."""
    if not app.state.service_status.is_ready:
        return
    options = _get_cycle_thinking_options(app.catalog_service, app.settings)
    result = app.cycle_thinking(options)
    if result.ok:
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
        await _handle_enter(app)

    @kb.add(Keys.ControlJ)
    def _newline(event: KeyPressEvent) -> None:
        event.current_buffer.insert_text("\n")

    @kb.add(Keys.ControlC)
    def _cancel_or_exit(_event: KeyPressEvent) -> None:
        _handle_cancel_or_exit(app)

    @kb.add(Keys.Escape, filter=_cancelable(app))
    def _escape(_event: KeyPressEvent) -> None:
        _handle_escape(app)

    @kb.add(Keys.ControlP)
    def _toggle_palette(_event: KeyPressEvent) -> None:
        app.toggle_palette()

    @kb.add(Keys.ControlT)
    def _cycle_thinking(_event: KeyPressEvent) -> None:
        _handle_cycle_thinking(app)

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
    def _clear_queue(_event: KeyPressEvent) -> None:
        app.dequeue_all()

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
