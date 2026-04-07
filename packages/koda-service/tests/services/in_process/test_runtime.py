from uuid import uuid4

import pytest

from koda.llm.types import LLMResponse, LLMResponseCompleted
from koda.llm.types import LLMTextDelta as CoreTextDelta
from koda.messages import AssistantMessage, TokenUsage
from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import UserMessage as CoreUserMessage
from koda.sessions import Session
from koda.sessions.exceptions import NoActiveSessionError, SessionNotFoundError
from koda_service.exceptions import (
    ServiceAuthenticationError,
    ServiceConnectionError,
    ServiceNoActiveSessionError,
    ServiceProviderError,
    ServiceRateLimitError,
    ServiceSessionNotFoundError,
)
from koda_service.services.in_process.runtime import InProcessKodaRuntime
from koda_service.types import ResponseCompleted, TextDelta, UserMessage

from .test_fakes import (
    FakeAgent,
    FakeAgentBehavior,
    RaisingApiAgent,
    RaisingAuthAgent,
    RaisingConnectionAgent,
    RaisingRateLimitAgent,
    core_session,
)

EXPECTED_MESSAGE_COUNT = 2


@pytest.mark.asyncio
async def test_chat_maps_core_events_to_stream_events() -> None:
    runtime = InProcessKodaRuntime(FakeAgent(events=[CoreTextDelta(text="hello")]))

    events = [event async for event in runtime.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], TextDelta)
    assert events[0].text == "hello"


@pytest.mark.asyncio
async def test_chat_maps_response_completed_usage_to_stream_event() -> None:
    runtime = InProcessKodaRuntime(
        FakeAgent(
            events=[
                LLMResponseCompleted(
                    response=LLMResponse(
                        output=AssistantMessage(content="done"),
                        usage=TokenUsage(
                            input_tokens=1_200,
                            output_tokens=300,
                            cached_tokens=50,
                            total_tokens=1_500,
                        ),
                    )
                )
            ]
        )
    )

    events = [event async for event in runtime.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], ResponseCompleted)
    assert events[0].output.content == "done"
    assert events[0].output.thinking_content == ""
    assert events[0].usage is not None
    assert events[0].usage.input_tokens == 1_200
    assert events[0].usage.output_tokens == 300


@pytest.mark.asyncio
async def test_chat_maps_auth_error_to_service_auth_error() -> None:
    runtime = InProcessKodaRuntime(RaisingAuthAgent())

    with pytest.raises(ServiceAuthenticationError):
        _ = [event async for event in runtime.chat("hi")]


@pytest.mark.asyncio
async def test_chat_maps_rate_limit_error_to_service_rate_limit_error() -> None:
    runtime = InProcessKodaRuntime(RaisingRateLimitAgent())

    with pytest.raises(ServiceRateLimitError):
        _ = [event async for event in runtime.chat("hi")]


@pytest.mark.asyncio
async def test_chat_maps_connection_error_to_service_connection_error() -> None:
    runtime = InProcessKodaRuntime(RaisingConnectionAgent())

    with pytest.raises(ServiceConnectionError):
        _ = [event async for event in runtime.chat("hi")]


@pytest.mark.asyncio
async def test_chat_maps_api_error_to_service_provider_error() -> None:
    runtime = InProcessKodaRuntime(RaisingApiAgent())

    with pytest.raises(ServiceProviderError):
        _ = [event async for event in runtime.chat("hi")]


def test_active_session_maps_session_info() -> None:
    session = core_session(name="Current Session")
    runtime = InProcessKodaRuntime(FakeAgent(behavior=FakeAgentBehavior(active_session=session)))

    mapped = runtime.active_session()

    assert mapped.session_id == session.session_id
    assert mapped.name == "Current Session"


def test_active_session_maps_no_active_session_error() -> None:
    runtime = InProcessKodaRuntime(
        FakeAgent(behavior=FakeAgentBehavior(errors={"active_session": NoActiveSessionError()}))
    )

    with pytest.raises(ServiceNoActiveSessionError):
        runtime.active_session()


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
    runtime = InProcessKodaRuntime(FakeAgent(session=session))

    mapped_session, mapped_messages = runtime.switch_session(session_id)

    assert mapped_session.session_id == session_id
    assert mapped_session.name == "Example Session"
    assert len(mapped_messages) == EXPECTED_MESSAGE_COUNT
    assert isinstance(mapped_messages[0], UserMessage)
    assert mapped_messages[0].content == "hello"


def test_switch_session_maps_session_not_found_error() -> None:
    session_id = uuid4()
    runtime = InProcessKodaRuntime(
        FakeAgent(
            behavior=FakeAgentBehavior(errors={"switch_session": SessionNotFoundError(session_id)})
        )
    )

    with pytest.raises(ServiceSessionNotFoundError):
        runtime.switch_session(session_id)


def test_list_sessions_filters_empty_sessions() -> None:
    non_empty = core_session(content="keep me")
    runtime = InProcessKodaRuntime(
        FakeAgent(
            sessions=[Session(), non_empty],
            session=non_empty,
        )
    )

    sessions = runtime.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].name.startswith("keep me")


def test_new_session_maps_session_info() -> None:
    session = core_session(content="new content")
    runtime = InProcessKodaRuntime(FakeAgent(session=session))

    mapped = runtime.new_session()

    assert mapped.session_id == session.session_id
    assert mapped.message_count == 1


def test_delete_session_returns_none_when_core_returns_none() -> None:
    runtime = InProcessKodaRuntime(FakeAgent(behavior=FakeAgentBehavior(delete_return=None)))

    assert runtime.delete_session(uuid4()) is None


def test_delete_session_maps_session_when_core_returns_session() -> None:
    returned = core_session(content="after delete", name="Recovered")
    runtime = InProcessKodaRuntime(FakeAgent(behavior=FakeAgentBehavior(delete_return=returned)))

    mapped = runtime.delete_session(uuid4())

    assert mapped is not None
    assert mapped.name == "Recovered"


def test_delete_session_maps_session_not_found_error() -> None:
    session_id = uuid4()
    runtime = InProcessKodaRuntime(
        FakeAgent(
            behavior=FakeAgentBehavior(errors={"delete_session": SessionNotFoundError(session_id)})
        )
    )

    with pytest.raises(ServiceSessionNotFoundError):
        runtime.delete_session(session_id)
