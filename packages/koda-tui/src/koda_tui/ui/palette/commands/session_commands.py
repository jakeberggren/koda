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


_SESSION_FOOTER = [
    ("class:palette.item", "ctrl-n"),
    ("class:palette.hint", " new · "),
    ("class:palette.item", "ctrl-d"),
    ("class:palette.hint", " delete"),
]


def open_session_list(
    client: Client,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> None:
    """Open the session list palette."""
    commands, shortcuts = get_commands(client, state, palette_manager, cancel_streaming)
    palette_manager.open_palette(commands, footer=_SESSION_FOOTER, shortcuts=shortcuts)


def _format_session_label(session: SessionInfo, active_session: SessionInfo) -> str:
    """Format session label with timestamp, message count, and active status."""
    timestamp = session.created_at.strftime("%Y-%m-%d")
    label = f"{session.name}  [{timestamp}] ({session.message_count} messages)"
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
    _, core_messages = client.switch_session(session.session_id)
    state.messages = convert_messages(core_messages)
    palette_manager.close_all()


def _confirm_delete_session(
    session: SessionInfo,
    client: Client,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> None:
    """Open a confirmation dialog to delete a session."""

    def on_confirm() -> None:
        client.delete_session(session.session_id)
        # Replace confirm dialog + stale session list with a fresh session list.
        commands, shortcuts = get_commands(client, state, palette_manager, cancel_streaming)
        palette_manager.replace_top(2, commands, footer=_SESSION_FOOTER, shortcuts=shortcuts)

    palette_manager.open_confirm(
        message="Delete session?",
        on_confirm=on_confirm,
    )


def get_commands(  # noqa: C901
    client: Client,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> tuple[list[Command], dict[str, Callable[[Command | None], None]]]:
    """Get commands and shortcuts for the session list palette."""
    sessions = client.list_sessions()
    active = client.active_session()

    command_sessions: list[tuple[Command, SessionInfo]] = []
    for session in sessions:
        cmd = Command(
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
        command_sessions.append((cmd, session))

    commands = [cmd for cmd, _ in command_sessions]

    def on_new(_cmd: Command | None) -> None:
        cancel_streaming()
        client.new_session()
        state.reset_conversation()
        palette_manager.close_all()

    def on_delete(cmd: Command | None) -> None:
        if cmd is None:
            return
        for command, session in command_sessions:
            if command is cmd:
                _confirm_delete_session(
                    session,
                    client,
                    state,
                    palette_manager,
                    cancel_streaming,
                )
                return

    shortcuts: dict[str, Callable[[Command | None], None]] = {
        Keys.ControlN: on_new,
        Keys.ControlD: on_delete,
    }

    return commands, shortcuts
