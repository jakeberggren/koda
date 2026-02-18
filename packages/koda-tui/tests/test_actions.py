from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

from koda_common.contracts import (
    BackendNoActiveSessionError,
    BackendSessionNotFoundError,
    SessionInfo,
    UserMessage,
)
from koda_tui.actions import delete_session, new_session, switch_session
from koda_tui.state import AppState, Message, MessageRole


def _session_info() -> SessionInfo:
    return SessionInfo(
        session_id=uuid4(),
        name="Session",
        message_count=0,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _state_with_conversation() -> AppState:
    state = AppState(provider_name="openai", model_name="gpt-5.2")
    state.messages = [Message(role=MessageRole.USER, content="old")]
    state.current_streaming_content = "partial"
    state.is_streaming = True
    return state


def test_new_session_success_resets_state() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["new_session"])
    backend.new_session.return_value = _session_info()

    result = new_session(backend, state)

    assert result.ok is True
    assert result.error is None
    backend.new_session.assert_called_once_with()
    assert state.messages == []
    assert state.current_streaming_content == ""
    assert state.is_streaming is False


def test_new_session_returns_error_when_no_active_session() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["new_session"])
    backend.new_session.side_effect = BackendNoActiveSessionError

    result = new_session(backend, state)

    assert result.ok is False
    assert result.error == "No active session available"
    assert state.messages[0].content == "old"


def test_switch_session_success_converts_messages() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["switch_session"])
    backend.switch_session.return_value = (_session_info(), [UserMessage(content="hello")])
    session_id = uuid4()

    result = switch_session(session_id, backend, state)

    assert result.ok is True
    backend.switch_session.assert_called_once_with(session_id)
    assert len(state.messages) == 1
    assert state.messages[0].role == MessageRole.USER
    assert state.messages[0].content == "hello"


def test_switch_session_not_found_returns_error() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["switch_session"])
    backend.switch_session.side_effect = BackendSessionNotFoundError

    result = switch_session(uuid4(), backend, state)

    assert result.ok is False
    assert result.error == "Session not found"
    assert state.messages[0].content == "old"
    assert state.current_streaming_content == "partial"
    assert state.is_streaming is True


def test_delete_session_active_removed_resets_state() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["delete_session"])
    backend.delete_session.return_value = _session_info()
    session_id = uuid4()

    result = delete_session(session_id, backend, state)

    assert result.ok is True
    assert result.payload is not None
    assert result.payload.removed_active_session is True
    backend.delete_session.assert_called_once_with(session_id)
    assert state.messages == []


def test_delete_session_non_active_keeps_state() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["delete_session"])
    backend.delete_session.return_value = None

    result = delete_session(uuid4(), backend, state)

    assert result.ok is True
    assert result.payload is not None
    assert result.payload.removed_active_session is False
    assert state.messages[0].content == "old"


def test_delete_session_not_found_returns_error() -> None:
    state = _state_with_conversation()
    backend = Mock(spec=["delete_session"])
    backend.delete_session.side_effect = BackendSessionNotFoundError

    result = delete_session(uuid4(), backend, state)

    assert result.ok is False
    assert result.error == "Session not found"
    assert state.messages[0].content == "old"
