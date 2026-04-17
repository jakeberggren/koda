from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from koda_service.types import SessionInfo
from koda_tui.state import AppState
from koda_tui.ui.palette.commands.session_commands import get_commands


def _session_info(*, name: str = "Session", message_count: int = 0) -> SessionInfo:
    return SessionInfo(
        session_id=uuid4(),
        name=name,
        message_count=message_count,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_get_commands_handles_no_active_session(state: AppState) -> None:
    session = _session_info(name="Existing session", message_count=2)
    service = Mock(spec=["list_sessions", "active_session"])
    service.list_sessions.return_value = [session]
    service.active_session.return_value = None

    commands, shortcuts = get_commands(
        service,
        state,
        palette_manager=Mock(),
        cancel_streaming=Mock(),
    )

    assert len(commands) == 1
    assert commands[0].label == "Existing session  [2026-01-01] (2 messages)"
    assert shortcuts


def test_get_commands_handles_no_sessions_and_no_active_session(state: AppState) -> None:
    service = Mock(spec=["list_sessions", "active_session"])
    service.list_sessions.return_value = []
    service.active_session.return_value = None

    commands, shortcuts = get_commands(
        service,
        state,
        palette_manager=Mock(),
        cancel_streaming=Mock(),
    )

    assert commands == []
    assert shortcuts
