"""Tests for sessions/memory.py - InMemorySessionStore."""

import uuid

import pytest

from koda.messages import UserMessage
from koda.sessions import (
    InMemorySessionStore,
    Session,
    SessionNotFoundError,
)


class TestInMemorySessionStore:
    def test_create_session(self) -> None:
        store = InMemorySessionStore()

        session = store.create_session(name="test")

        assert isinstance(session.session_id, uuid.UUID)
        assert session.name == "test"
        assert session.messages == []

    def test_create_session_without_name(self) -> None:
        store = InMemorySessionStore()

        session = store.create_session()

        assert isinstance(session.session_id, uuid.UUID)
        assert session.name is None
        assert session.messages == []

    def test_create_session_generates_unique_ids(self) -> None:
        store = InMemorySessionStore()

        session_a = store.create_session()
        session_b = store.create_session()

        assert session_a.session_id != session_b.session_id

    def test_get_session(self) -> None:
        store = InMemorySessionStore()
        created = store.create_session(name="test")

        session = store.get_session(created.session_id)

        assert session.session_id == created.session_id

    def test_get_session_not_found(self) -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            store.get_session(uuid.uuid4())

    def test_list_sessions(self) -> None:
        store = InMemorySessionStore()
        store.create_session(name="first")
        store.create_session(name="second")

        sessions = store.list_sessions()

        names = {s.name for s in sessions}
        assert names == {"first", "second"}

    def test_list_sessions_empty(self) -> None:
        store = InMemorySessionStore()

        assert store.list_sessions() == []

    def test_update_session(self) -> None:
        store = InMemorySessionStore()
        created = store.create_session(name="test")

        msg = UserMessage(content="hello")
        updated = Session(session_id=created.session_id, name="test", messages=[msg])
        result = store.update_session(updated)

        assert result.messages == [msg]
        assert store.get_session(created.session_id).messages == [msg]

    def test_update_session_not_found(self) -> None:
        store = InMemorySessionStore()
        session = Session(session_id=uuid.uuid4(), name="ghost", messages=[])

        with pytest.raises(SessionNotFoundError):
            store.update_session(session)

    def test_delete_session(self) -> None:
        store = InMemorySessionStore()
        session = store.create_session(name="test")

        store.delete_session(session.session_id)

        with pytest.raises(SessionNotFoundError):
            store.get_session(session.session_id)

    def test_delete_session_not_found(self) -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            store.delete_session(uuid.uuid4())

    def test_append_message(self) -> None:
        store = InMemorySessionStore()
        created = store.create_session(name="test")
        msg = UserMessage(content="hello")

        result = store.append_message(created.session_id, msg)

        assert result.messages == [msg]
        assert store.get_session(created.session_id).messages == [msg]

    def test_append_message_not_found(self) -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            store.append_message(uuid.uuid4(), UserMessage(content="hello"))
