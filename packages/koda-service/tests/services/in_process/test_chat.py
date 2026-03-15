import pytest

from koda.llm.types import LLMTextDelta as CoreTextDelta
from koda_service.exceptions import ServiceAuthenticationError
from koda_service.services.in_process.chat import ChatService
from koda_service.types import TextDelta

from .test_fakes import FakeAgent, RaisingAuthAgent


@pytest.mark.asyncio
async def test_chat_maps_core_events_to_stream_events() -> None:
    service = ChatService(FakeAgent(events=[CoreTextDelta(text="hello")]))

    events = [event async for event in service.chat("hi")]

    assert len(events) == 1
    assert isinstance(events[0], TextDelta)
    assert events[0].text == "hello"


@pytest.mark.asyncio
async def test_chat_maps_auth_error_to_service_auth_error() -> None:
    service = ChatService(RaisingAuthAgent())

    with pytest.raises(ServiceAuthenticationError):
        _ = [event async for event in service.chat("hi")]
