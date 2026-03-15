from uuid import uuid4

import pytest

from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import UserMessage as CoreUserMessage
from koda.sessions import Session
from koda.sessions.exceptions import NoActiveSessionError, SessionNotFoundError
from koda_service.exceptions import (
    ServiceNoActiveSessionError,
    ServiceSessionNotFoundError,
)
from koda_service.services.in_process.sessions import SessionService
from koda_service.types import UserMessage

from .test_fakes import FakeAgent, FakeAgentBehavior, core_session

EXPECTED_MESSAGE_COUNT = 2


def test_active_session_maps_session_info() -> None:
    session = core_session(name="Current Session")
    service = SessionService(FakeAgent(behavior=FakeAgentBehavior(active_session=session)))

    mapped = service.active_session()

    assert mapped.session_id == session.session_id
    assert mapped.name == "Current Session"


def test_active_session_maps_no_active_session_error() -> None:
    service = SessionService(
        FakeAgent(behavior=FakeAgentBehavior(errors={"active_session": NoActiveSessionError()}))
    )

    with pytest.raises(ServiceNoActiveSessionError):
        service.active_session()


def test_switch_session_returns_service_session_and_messages() -> None:
    session_id = uuid4()
    session = Session(
        session_id=session_id,
        messages=[
            CoreUserMessage(content="hello"),
            CoreAssistantMessage(content="hi there"),
        ],
        name="Example Session",
    )
    service = SessionService(FakeAgent(session=session))

    mapped_session, mapped_messages = service.switch_session(session_id)

    assert mapped_session.session_id == session_id
    assert mapped_session.name == "Example Session"
    assert len(mapped_messages) == EXPECTED_MESSAGE_COUNT
    assert isinstance(mapped_messages[0], UserMessage)
    assert mapped_messages[0].content == "hello"


def test_switch_session_maps_session_not_found_error() -> None:
    session_id = uuid4()
    service = SessionService(
        FakeAgent(
            behavior=FakeAgentBehavior(errors={"switch_session": SessionNotFoundError(session_id)})
        )
    )

    with pytest.raises(ServiceSessionNotFoundError):
        service.switch_session(session_id)


def test_list_sessions_filters_empty_sessions() -> None:
    non_empty = core_session(content="keep me")
    service = SessionService(
        FakeAgent(
            sessions=[Session(), non_empty],
            session=non_empty,
        )
    )

    sessions = service.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].name.startswith("keep me")


def test_new_session_maps_session_info() -> None:
    session = core_session(content="new content")
    service = SessionService(FakeAgent(session=session))

    mapped = service.new_session()

    assert mapped.session_id == session.session_id
    assert mapped.message_count == 1


def test_delete_session_returns_none_when_core_returns_none() -> None:
    service = SessionService(FakeAgent(behavior=FakeAgentBehavior(delete_return=None)))

    assert service.delete_session(uuid4()) is None


def test_delete_session_maps_session_when_core_returns_session() -> None:
    returned = core_session(content="after delete", name="Recovered")
    service = SessionService(FakeAgent(behavior=FakeAgentBehavior(delete_return=returned)))

    mapped = service.delete_session(uuid4())

    assert mapped is not None
    assert mapped.name == "Recovered"


def test_delete_session_maps_session_not_found_error() -> None:
    session_id = uuid4()
    service = SessionService(
        FakeAgent(
            behavior=FakeAgentBehavior(errors={"delete_session": SessionNotFoundError(session_id)})
        )
    )

    with pytest.raises(ServiceSessionNotFoundError):
        service.delete_session(session_id)
