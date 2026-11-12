"""Tests for koda.sessions.store."""

import uuid
from pathlib import Path

import pytest

from koda.messages import AssistantMessage, TokenUsage, ToolMessage, UserMessage
from koda.sessions import (
    InMemorySessionStore,
    JsonSessionStore,
    Session,
    SessionNotFoundError,
    SessionStore,
)
from koda.tools.base import ToolCall, ToolOutput, ToolResult


@pytest.fixture(params=["memory", "json"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> SessionStore:
    if request.param == "memory":
        return InMemorySessionStore()
    return JsonSessionStore(directory=tmp_path)


class TestSessionStore:
    def test_save_and_get_session(self, store: SessionStore) -> None:
        session = Session(messages=[UserMessage(content="hello")])

        store.save_session(session)

        assert store.get_session(session.session_id) == session

    def test_save_session_replaces_saved_session(self, store: SessionStore) -> None:
        session = Session()
        store.save_session(session)

        session.messages.append(UserMessage(content="hello"))
        store.save_session(session)

        assert store.get_session(session.session_id).messages == [UserMessage(content="hello")]

    def test_saved_session_is_independent_of_the_original(self, store: SessionStore) -> None:
        session = Session()
        store.save_session(session)

        session.messages.append(UserMessage(content="unsaved"))

        assert store.get_session(session.session_id).messages == []

    def test_get_session_not_found(self, store: SessionStore) -> None:
        with pytest.raises(SessionNotFoundError):
            store.get_session(uuid.uuid4())

    def test_list_sessions_newest_first(self, store: SessionStore) -> None:
        older = Session()
        newer = Session()
        store.save_session(older)
        store.save_session(newer)

        assert [s.session_id for s in store.list_sessions()] == [
            newer.session_id,
            older.session_id,
        ]

    def test_list_sessions_empty(self, store: SessionStore) -> None:
        assert store.list_sessions() == []

    def test_delete_session(self, store: SessionStore) -> None:
        session = Session()
        store.save_session(session)

        store.delete_session(session.session_id)

        with pytest.raises(SessionNotFoundError):
            store.get_session(session.session_id)

    def test_delete_session_not_found(self, store: SessionStore) -> None:
        with pytest.raises(SessionNotFoundError):
            store.delete_session(uuid.uuid4())


class TestSessionUsage:
    def test_usage_returns_latest_assistant_usage(self) -> None:
        first_usage = TokenUsage(input_tokens=10, output_tokens=2, total_tokens=12)
        latest_usage = TokenUsage(input_tokens=20, output_tokens=4, total_tokens=24)
        session = Session(
            messages=[
                AssistantMessage(content="one", usage=first_usage),
                UserMessage(content="next"),
                AssistantMessage(content="two"),
                AssistantMessage(content="three", usage=latest_usage),
            ]
        )

        assert session.usage == latest_usage

    def test_usage_returns_none_without_assistant_usage(self) -> None:
        session = Session(
            messages=[
                UserMessage(content="hello"),
                AssistantMessage(content="hi"),
            ]
        )

        assert session.usage is None
        assert session.total_usage is None

    def test_total_usage_sums_assistant_usage(self) -> None:
        session = Session(
            messages=[
                AssistantMessage(
                    content="one",
                    usage=TokenUsage(
                        input_tokens=10,
                        output_tokens=2,
                        cached_tokens=1,
                        total_tokens=12,
                    ),
                ),
                UserMessage(content="next"),
                AssistantMessage(
                    content="two",
                    usage=TokenUsage(
                        input_tokens=20,
                        output_tokens=4,
                        cached_tokens=None,
                        total_tokens=24,
                    ),
                ),
            ]
        )

        assert session.total_usage == TokenUsage(
            input_tokens=30,
            output_tokens=6,
            cached_tokens=1,
            total_tokens=36,
        )


class TestJsonSessionStore:
    def test_directory_auto_creation(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        store = JsonSessionStore(directory=nested)

        session = Session()
        store.save_session(session)

        assert nested.is_dir()
        assert store.get_session(session.session_id).session_id == session.session_id

    def test_message_polymorphism_round_trip(self, tmp_path: Path) -> None:
        """Verify subclass-specific fields survive JSON serialization."""
        store = JsonSessionStore(directory=tmp_path)
        session = Session()

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

        session.messages.extend([assistant_msg, tool_msg])
        store.save_session(session)

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
