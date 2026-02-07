"""Tests for sessions/base.py - SessionManager."""

import uuid

import pytest

from koda.sessions import (
    ActiveSessionError,
    InMemorySessionStore,
    NoActiveSessionError,
    SessionManager,
    SessionNotFoundError,
)


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(InMemorySessionStore())


class TestSessionManager:
    def test_active_session_raises_when_none(self, manager: SessionManager) -> None:
        with pytest.raises(NoActiveSessionError):
            _ = manager.active_session

    def test_create_session_sets_active(self, manager: SessionManager) -> None:
        session = manager.create_session(name="test")

        assert manager.active_session.session_id == session.session_id

    def test_create_session_updates_active(self, manager: SessionManager) -> None:
        first = manager.create_session(name="first")

        second = manager.create_session(name="second")

        assert manager.active_session.session_id == second.session_id
        assert manager.active_session.session_id != first.session_id

    def test_switch_session(self, manager: SessionManager) -> None:
        first = manager.create_session(name="first")
        manager.create_session(name="second")

        result = manager.switch_session(first.session_id)

        assert result.session_id == first.session_id
        assert manager.active_session.session_id == first.session_id

    def test_switch_session_not_found(self, manager: SessionManager) -> None:
        with pytest.raises(SessionNotFoundError):
            manager.switch_session(uuid.uuid4())

    def test_delete_active_session_raises(self, manager: SessionManager) -> None:
        session = manager.create_session(name="test")

        with pytest.raises(ActiveSessionError):
            manager.delete_session(session.session_id)

    def test_delete_inactive_session(self, manager: SessionManager) -> None:
        first = manager.create_session(name="first")
        manager.create_session(name="second")

        manager.delete_session(first.session_id)

        session_ids = {s.session_id for s in manager.list_sessions()}
        assert first.session_id not in session_ids

    def test_list_sessions_delegates(self, manager: SessionManager) -> None:
        manager.create_session(name="first")
        manager.create_session(name="second")

        sessions = manager.list_sessions()

        names = {s.name for s in sessions}
        assert names == {"first", "second"}
