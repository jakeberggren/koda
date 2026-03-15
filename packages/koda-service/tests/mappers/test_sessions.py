from datetime import UTC, datetime
from uuid import UUID

from koda.messages import UserMessage
from koda.sessions import Session as CoreSession
from koda_service.mappers import map_session_to_session_info


def test_map_session_to_session_info_uses_explicit_name() -> None:
    session = CoreSession(
        session_id=UUID("00000000-0000-0000-0000-000000000001"),
        created_at=datetime(2026, 3, 15, tzinfo=UTC),
        name="My session",
        messages=[UserMessage(content="Hello")],
    )

    session_info = map_session_to_session_info(session)

    assert session_info.name == "My session"
    assert session_info.message_count == 1


def test_map_session_to_session_info_uses_first_message_prefix() -> None:
    session = CoreSession(
        messages=[UserMessage(content="A" * 40)],
    )

    session_info = map_session_to_session_info(session)

    assert session_info.name == f"{'A' * 30}..."
    assert session_info.message_count == 1


def test_map_session_to_session_info_uses_default_name_for_empty_session() -> None:
    session_info = map_session_to_session_info(CoreSession())

    assert session_info.name == "New session"
    assert session_info.message_count == 0
