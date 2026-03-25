"""Tests for sessions/base.py - SessionManager."""

import uuid

import pytest

from koda.messages import UserMessage
from koda.sessions import (
    InMemorySessionStore,
    NoActiveSessionError,
    SessionManager,
    SessionNotFoundError,
)


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(InMemorySessionStore())


def _add_message(manager: SessionManager, session_id: uuid.UUID) -> None:
    """Add a dummy message so the session is non-empty."""
    manager.append_message(session_id, UserMessage(content="hello"))


class TestSessionManager:
    def test_active_session_raises_when_none(self, manager: SessionManager) -> None:
        with pytest.raises(NoActiveSessionError):
            _ = manager.active_session

    def test_create_session_sets_active(self, manager: SessionManager) -> None:
        session = manager.create_session()

        assert manager.active_session.session_id == session.session_id

    def test_create_session_updates_active(self, manager: SessionManager) -> None:
        first = manager.create_session()
        _add_message(manager, first.session_id)

        second = manager.create_session()

        assert manager.active_session.session_id == second.session_id
        assert manager.active_session.session_id != first.session_id

    def test_switch_session(self, manager: SessionManager) -> None:
        first = manager.create_session()
        _add_message(manager, first.session_id)
        second = manager.create_session()
        _add_message(manager, second.session_id)

        result = manager.switch_session(first.session_id)

        assert result.session_id == first.session_id
        assert manager.active_session.session_id == first.session_id

    def test_switch_session_not_found(self, manager: SessionManager) -> None:
        with pytest.raises(SessionNotFoundError):
            manager.switch_session(uuid.uuid4())

    def test_delete_active_session_creates_new(self, manager: SessionManager) -> None:
        session = manager.create_session()
        _add_message(manager, session.session_id)

        new_session = manager.delete_session(session.session_id)

        assert new_session is not None
        assert new_session.session_id != session.session_id
        assert manager.active_session.session_id == new_session.session_id

    def test_delete_inactive_session(self, manager: SessionManager) -> None:
        first = manager.create_session()
        _add_message(manager, first.session_id)
        second = manager.create_session()
        _add_message(manager, second.session_id)

        result = manager.delete_session(first.session_id)

        assert result is None
        session_ids = {s.session_id for s in manager.list_sessions()}
        assert first.session_id not in session_ids

    def test_list_sessions_delegates(self, manager: SessionManager) -> None:
        first = manager.create_session()
        _add_message(manager, first.session_id)
        second = manager.create_session()
        _add_message(manager, second.session_id)

        sessions = manager.list_sessions()

        assert len(sessions) == 2

    def test_create_session_cleans_up_empty_active(self, manager: SessionManager) -> None:
        empty = manager.create_session()

        manager.create_session()

        session_ids = {s.session_id for s in manager.list_sessions()}
        assert empty.session_id not in session_ids

    def test_switch_session_cleans_up_empty_active(self, manager: SessionManager) -> None:
        first = manager.create_session()
        _add_message(manager, first.session_id)
        empty = manager.create_session()

        manager.switch_session(first.session_id)

        session_ids = {s.session_id for s in manager.list_sessions()}
        assert empty.session_id not in session_ids

    def test_switch_to_active_empty_session(self, manager: SessionManager) -> None:
        session = manager.create_session()

        result = manager.switch_session(session.session_id)

        assert result.session_id == session.session_id

    def test_create_session_keeps_non_empty_active(self, manager: SessionManager) -> None:
        first = manager.create_session()
        _add_message(manager, first.session_id)

        manager.create_session()

        session_ids = {s.session_id for s in manager.list_sessions()}
        assert first.session_id in session_ids
