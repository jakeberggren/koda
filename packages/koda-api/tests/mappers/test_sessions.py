from datetime import UTC, datetime
from uuid import uuid4

from koda.messages import UserMessage
from koda.sessions import Session
from koda_api.mappers import map_session_to_session_info


def test_map_session_to_session_info_uses_name_when_present() -> None:
    session = Session(
        session_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        name="My Session",
    )

    mapped = map_session_to_session_info(session)

    assert mapped.name == "My Session"
    assert mapped.message_count == 0


def test_map_session_to_session_info_uses_first_message_preview() -> None:
    session = Session(
        messages=[UserMessage(content="012345678901234567890123456789XYZ")],
    )

    mapped = map_session_to_session_info(session)

    assert mapped.name == "012345678901234567890123456789..."
    assert mapped.message_count == 1


def test_map_session_to_session_info_uses_new_session_fallback() -> None:
    session = Session()

    mapped = map_session_to_session_info(session)

    assert mapped.name == "New session"
    assert mapped.message_count == 0
