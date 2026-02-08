from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from prompt_toolkit.keys import Keys

from koda_tui.converters import convert_messages
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_tui.clients import Client, SessionInfo
    from koda_tui.state import AppState
    from koda_tui.ui.palette.palette_manager import PaletteManager


def _format_session_label(session: SessionInfo, active_session: SessionInfo) -> str:
    """Format session label with active status and message count."""
    label = f"{session.name}  ({session.message_count} messages)"
    if session.session_id == active_session.session_id:
        label += " [active]"
    return label


def _switch_session(
    session: SessionInfo,
    client: Client,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> None:
    """Switch to a session and update TUI state."""
    cancel_streaming()
    state.reset_conversation()
    client.switch_session(session.session_id)
    core_messages = client.get_session_messages(session.session_id)
    state.messages = convert_messages(core_messages)
    palette_manager.close_all()


def _confirm_delete_session(
    session: SessionInfo,
    client: Client,
    palette_manager: PaletteManager,
) -> None:
    """Open a confirmation dialog to delete a session."""

    def on_confirm() -> None:
        client.delete_session(session.session_id)
        palette_manager.close_all()

    palette_manager.open_confirm(
        message="Delete session?",
        on_confirm=on_confirm,
    )


def _get_shortcuts(  # noqa: C901
    client: Client,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> dict[str, Callable[[Command | None], None]]:
    """Build keyboard shortcuts for the session palette."""

    def on_new(_cmd: Command | None) -> None:
        cancel_streaming()
        client.new_session()
        state.reset_conversation()
        palette_manager.close_all()

    def on_delete(cmd: Command | None) -> None:
        if cmd is None:
            return
        # Find matching session by label
        sessions = client.list_sessions()
        active = client.active_session()
        for session in sessions:
            if _format_session_label(session, active) == cmd.label:
                _confirm_delete_session(session, client, palette_manager)
                return

    return {
        Keys.ControlN: on_new,
        Keys.ControlD: on_delete,
    }


def get_commands(
    client: Client,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> tuple[list[Command], dict[str, Callable[[Command | None], None]]]:
    """Get commands and shortcuts for the session list palette."""
    sessions = client.list_sessions()
    active = client.active_session()

    commands = [
        Command(
            label=_format_session_label(session, active),
            handler=partial(
                _switch_session,
                session,
                client,
                state,
                palette_manager,
                cancel_streaming,
            ),
        )
        for session in sessions
    ]

    shortcuts = _get_shortcuts(client, state, palette_manager, cancel_streaming)

    return commands, shortcuts
