from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from prompt_toolkit.keys import Keys

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_service.types import SessionInfo
    from koda_tui.actions import ActionResult, DeleteSessionPayload
    from koda_tui.bootstrap.manager import KodaRuntimeManager
    from koda_tui.state import AppState
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)


_SESSION_FOOTER: StyleAndTextTuples = [
    ("class:palette.item", "ctrl-n"),
    ("class:palette.hint", " new · "),
    ("class:palette.item", "ctrl-d"),
    ("class:palette.hint", " delete"),
]


def open_session_list(
    runtime_manager: KodaRuntimeManager,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> None:
    """Open the session list palette."""
    commands, shortcuts = get_commands(runtime_manager, state, palette_manager, cancel_streaming)
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
    runtime_manager: KodaRuntimeManager,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> None:
    """Switch to a session and update TUI state."""
    cancel_streaming()
    runtime = runtime_manager.get_runtime()
    result = actions.switch_session(session.session_id, runtime, state)
    if not result.ok:
        log.warning(
            "cmd_switch_session_failed",
            session_id=str(session.session_id),
            error=result.error,
        )
        # TODO: surface action errors in the palette/status UI.
        return
    palette_manager.close_all()


def _confirm_delete_session(
    session: SessionInfo,
    runtime_manager: KodaRuntimeManager,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> None:
    """Open a confirmation dialog to delete a session."""

    def on_confirm() -> None:
        service = runtime_manager.get_runtime()
        result: ActionResult[DeleteSessionPayload] = actions.delete_session(
            session.session_id, service, state
        )
        if not result.ok:
            log.warning(
                "cmd_delete_session_failed",
                session_id=str(session.session_id),
                error=result.error,
            )
            # TODO: surface action errors in the palette/status UI.
            return
        if result.ok and result.payload and result.payload.removed_active_session:
            # On deletion of the active session, clear stale messages from the screen.
            cancel_streaming()
        # Replace confirm dialog + stale session list with a fresh session list.
        commands, shortcuts = get_commands(
            runtime_manager,
            state,
            palette_manager,
            cancel_streaming,
        )
        palette_manager.replace_top(2, commands, footer=_SESSION_FOOTER, shortcuts=shortcuts)

    palette_manager.open_confirm(
        message="Delete session?",
        on_confirm=on_confirm,
    )


def get_commands(  # noqa: C901
    runtime_manager: KodaRuntimeManager,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> tuple[list[Command], dict[str, Callable[[Command | None], None]]]:
    """Get commands and shortcuts for the session list palette."""
    service = runtime_manager.get_runtime()
    sessions = service.list_sessions()
    active = service.active_session()

    command_sessions: list[tuple[Command, SessionInfo]] = []
    for session in sessions:
        cmd = Command(
            label=_format_session_label(session, active),
            handler=partial(
                _switch_session,
                session,
                runtime_manager,
                state,
                palette_manager,
                cancel_streaming,
            ),
        )
        command_sessions.append((cmd, session))

    commands = [cmd for cmd, _ in command_sessions]

    def on_new(_cmd: Command | None) -> None:
        cancel_streaming()
        service = runtime_manager.get_runtime()
        result = actions.new_session(service, state)
        if not result.ok:
            log.warning("cmd_new_session_shortcut_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def on_delete(cmd: Command | None) -> None:
        if cmd is None:
            return
        for command, session in command_sessions:
            if command is cmd:
                _confirm_delete_session(
                    session,
                    runtime_manager,
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
