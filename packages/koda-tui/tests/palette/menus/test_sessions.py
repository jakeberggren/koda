from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from koda.sessions import Session
from koda_tui.actions import ActionResult, DeleteSessionPayload
from koda_tui.palette.menus.sessions import SessionMenu


def _session(name: str) -> Session:
    return Session(
        session_id=uuid4(),
        name=name,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _palette(service: Mock | None = None) -> Mock:
    palette = Mock(spec=["service", "state", "cancel_streaming", "close_all_overlays"])
    palette.service = service or Mock()
    palette.state = Mock()
    return palette


def test_items_marks_active_session() -> None:
    active = _session("Active")
    inactive = _session("Inactive")
    service = Mock(spec=["active_session", "list_sessions"])
    service.active_session.return_value = active
    service.list_sessions.return_value = [inactive, active]

    items = SessionMenu(_palette(service)).items()

    assert items[0].marker is None
    assert items[0].marker_style is None
    assert items[1].marker == "*"
    assert items[1].marker_style == "class:palette.current"


def test_delete_cancels_streaming_when_active_session_removed() -> None:
    session = _session("Active")
    palette = _palette()

    with patch(
        "koda_tui.palette.menus.sessions.actions.delete_session",
        return_value=ActionResult(
            ok=True,
            payload=DeleteSessionPayload(removed_active_session=True),
        ),
    ) as delete_session:
        SessionMenu(palette).delete(session)

    delete_session.assert_called_once_with(session.session_id, palette.service, palette.state)
    palette.cancel_streaming.assert_called_once_with()
    palette.close_all_overlays.assert_called_once_with()


def test_delete_does_not_cancel_streaming_when_inactive_session_removed() -> None:
    session = _session("Inactive")
    palette = _palette()

    with patch(
        "koda_tui.palette.menus.sessions.actions.delete_session",
        return_value=ActionResult(
            ok=True,
            payload=DeleteSessionPayload(removed_active_session=False),
        ),
    ):
        SessionMenu(palette).delete(session)

    palette.cancel_streaming.assert_not_called()
    palette.close_all_overlays.assert_called_once_with()


def test_delete_does_not_cancel_or_close_on_failure() -> None:
    session = _session("Missing")
    palette = _palette()

    with patch(
        "koda_tui.palette.menus.sessions.actions.delete_session",
        return_value=ActionResult(ok=False, error="Session not found"),
    ):
        SessionMenu(palette).delete(session)

    palette.cancel_streaming.assert_not_called()
    palette.close_all_overlays.assert_not_called()
