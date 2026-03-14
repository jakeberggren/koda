"""Tests for sessions/memory.py - InMemorySessionStore."""

import uuid
from pathlib import Path

import pytest

from koda.messages import AssistantMessage, ToolMessage, UserMessage
from koda.sessions import (
    InMemorySessionStore,
    JsonSessionStore,
    Session,
    SessionNotFoundError,
)
from koda.tools.base import ToolCall, ToolOutput, ToolResult


class TestInMemorySessionStore:
    def test_create_session(self) -> None:
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
        created = store.create_session()

        session = store.get_session(created.session_id)

        assert session.session_id == created.session_id

    def test_get_session_not_found(self) -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            store.get_session(uuid.uuid4())

    def test_list_sessions(self) -> None:
        store = InMemorySessionStore()
        store.create_session()
        store.create_session()

        sessions = store.list_sessions()

        assert len(sessions) == 2  # noqa: PLR2004

    def test_list_sessions_empty(self) -> None:
        store = InMemorySessionStore()

        assert store.list_sessions() == []

    def test_update_session(self) -> None:
        store = InMemorySessionStore()
        created = store.create_session()

        updated = Session(session_id=created.session_id, name="renamed")
        result = store.update_session(updated)

        assert result.name == "renamed"
        assert store.get_session(created.session_id).name == "renamed"

    def test_update_session_not_found(self) -> None:
        store = InMemorySessionStore()
        session = Session(session_id=uuid.uuid4(), name="ghost")

        with pytest.raises(SessionNotFoundError):
            store.update_session(session)

    def test_delete_session(self) -> None:
        store = InMemorySessionStore()
        session = store.create_session()

        store.delete_session(session.session_id)

        with pytest.raises(SessionNotFoundError):
            store.get_session(session.session_id)

    def test_delete_session_not_found(self) -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            store.delete_session(uuid.uuid4())

    def test_append_message(self) -> None:
        store = InMemorySessionStore()
        created = store.create_session()
        msg = UserMessage(content="hello")

        result = store.append_message(created.session_id, msg)

        assert result.messages == [msg]
        assert store.get_session(created.session_id).messages == [msg]

    def test_append_message_not_found(self) -> None:
        store = InMemorySessionStore()

        with pytest.raises(SessionNotFoundError):
            store.append_message(uuid.uuid4(), UserMessage(content="hello"))


class TestJsonSessionStore:
    def test_create_session(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)

        session = store.create_session()

        assert isinstance(session.session_id, uuid.UUID)
        assert session.name is None
        assert session.messages == []
        assert (tmp_path / f"{session.session_id}.json").exists()

    def test_create_session_generates_unique_ids(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)

        session_a = store.create_session()
        session_b = store.create_session()

        assert session_a.session_id != session_b.session_id

    def test_get_session(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)
        created = store.create_session()

        session = store.get_session(created.session_id)

        assert session.session_id == created.session_id

    def test_get_session_not_found(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)

        with pytest.raises(SessionNotFoundError):
            store.get_session(uuid.uuid4())

    def test_list_sessions(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)
        store.create_session()
        store.create_session()

        sessions = store.list_sessions()

        assert len(sessions) == 2  # noqa: PLR2004

    def test_list_sessions_empty(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)

        assert store.list_sessions() == []

    def test_update_session(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)
        created = store.create_session()

        updated = Session(session_id=created.session_id, name="renamed")
        result = store.update_session(updated)

        assert result.name == "renamed"
        assert store.get_session(created.session_id).name == "renamed"

    def test_update_session_not_found(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)
        session = Session(session_id=uuid.uuid4(), name="ghost")

        with pytest.raises(SessionNotFoundError):
            store.update_session(session)

    def test_delete_session(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)
        session = store.create_session()

        store.delete_session(session.session_id)

        with pytest.raises(SessionNotFoundError):
            store.get_session(session.session_id)
        assert not (tmp_path / f"{session.session_id}.json").exists()

    def test_delete_session_not_found(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)

        with pytest.raises(SessionNotFoundError):
            store.delete_session(uuid.uuid4())

    def test_append_message(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)
        created = store.create_session()
        msg = UserMessage(content="hello")

        result = store.append_message(created.session_id, msg)

        assert len(result.messages) == 1
        assert result.messages[0].content == "hello"
        # Verify persistence
        reloaded = store.get_session(created.session_id)
        assert len(reloaded.messages) == 1
        assert reloaded.messages[0].content == "hello"

    def test_append_message_not_found(self, tmp_path: Path) -> None:
        store = JsonSessionStore(directory=tmp_path)

        with pytest.raises(SessionNotFoundError):
            store.append_message(uuid.uuid4(), UserMessage(content="hello"))

    def test_directory_auto_creation(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        store = JsonSessionStore(directory=nested)

        session = store.create_session()

        assert nested.is_dir()
        assert store.get_session(session.session_id).session_id == session.session_id

    def test_message_polymorphism_round_trip(self, tmp_path: Path) -> None:
        """Verify subclass-specific fields survive JSON serialization."""
        store = JsonSessionStore(directory=tmp_path)
        session = store.create_session()

        tool_call = ToolCall(tool_name="read_file", arguments={"path": "/tmp/x"}, call_id="tc_1")
        assistant_msg = AssistantMessage(
            content="Let me read that.",
            thinking_content="Need to inspect the file first.",
            tool_calls=[tool_call],
        )
        tool_msg = ToolMessage(
            content="file contents here",
            tool_name="read_file",
            tool_result=ToolResult(output=ToolOutput(content={"text": "hello"}), call_id="tc_1"),
        )

        store.append_message(session.session_id, assistant_msg)
        store.append_message(session.session_id, tool_msg)

        reloaded = store.get_session(session.session_id)

        # AssistantMessage.tool_calls preserved
        assert isinstance(reloaded.messages[0], AssistantMessage)
        assert reloaded.messages[0].thinking_content == "Need to inspect the file first."
        assert len(reloaded.messages[0].tool_calls) == 1
        assert reloaded.messages[0].tool_calls[0].tool_name == "read_file"
        assert reloaded.messages[0].tool_calls[0].call_id == "tc_1"

        # ToolMessage.tool_result preserved
        assert isinstance(reloaded.messages[1], ToolMessage)
        assert reloaded.messages[1].tool_name == "read_file"
        assert reloaded.messages[1].tool_result.call_id == "tc_1"
        assert reloaded.messages[1].tool_result.output.content == {"text": "hello"}
