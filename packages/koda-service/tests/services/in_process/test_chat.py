import pytest

from koda.llm.types import LLMResponse, LLMResponseCompleted, LLMTokenUsage
from koda.llm.types import LLMTextDelta as CoreTextDelta
from koda.messages import AssistantMessage
from koda_service.exceptions import (
    ServiceAuthenticationError,
    ServiceConnectionError,
    ServiceProviderError,
    ServiceRateLimitError,
)
from koda_service.services.in_process.chat import ChatService
from koda_service.types import ResponseCompleted, TextDelta

from .test_fakes import (
    FakeAgent,
    RaisingApiAgent,
    RaisingAuthAgent,
    RaisingConnectionAgent,
    RaisingRateLimitAgent,
)


@pytest.mark.asyncio
async def test_chat_maps_core_events_to_stream_events() -> None:
    service = ChatService(FakeAgent(events=[CoreTextDelta(text="hello")]))

    events = [event async for event in service.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], TextDelta)
    assert events[0].text == "hello"


@pytest.mark.asyncio
async def test_chat_maps_response_completed_usage_to_stream_event() -> None:
    service = ChatService(
        FakeAgent(
            events=[
                LLMResponseCompleted(
                    response=LLMResponse(
                        output=AssistantMessage(content="done"),
                        usage=LLMTokenUsage(
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

    events = [event async for event in service.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], ResponseCompleted)
    assert events[0].output.content == "done"
    assert events[0].output.thinking_content == ""
    assert events[0].usage is not None
    assert events[0].usage.input_tokens == 1_200
    assert events[0].usage.output_tokens == 300


@pytest.mark.asyncio
async def test_chat_maps_auth_error_to_service_auth_error() -> None:
    service = ChatService(RaisingAuthAgent())

    with pytest.raises(ServiceAuthenticationError):
        _ = [event async for event in service.chat("hi")]


@pytest.mark.asyncio
async def test_chat_maps_rate_limit_error_to_service_rate_limit_error() -> None:
    service = ChatService(RaisingRateLimitAgent())

    with pytest.raises(ServiceRateLimitError):
        _ = [event async for event in service.chat("hi")]


@pytest.mark.asyncio
async def test_chat_maps_connection_error_to_service_connection_error() -> None:
    service = ChatService(RaisingConnectionAgent())

    with pytest.raises(ServiceConnectionError):
        _ = [event async for event in service.chat("hi")]


@pytest.mark.asyncio
async def test_chat_maps_api_error_to_service_provider_error() -> None:
    service = ChatService(RaisingApiAgent())

    with pytest.raises(ServiceProviderError):
        _ = [event async for event in service.chat("hi")]
