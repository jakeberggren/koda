from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMRateLimitError,
)
from koda_service.exceptions import (
    ServiceAuthenticationError,
    ServiceChatError,
    ServiceConnectionError,
    ServiceProviderError,
    ServiceRateLimitError,
)
from koda_service.mappers import map_llm_event_to_stream_event

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda_service.types.events import StreamEvent


def _translate_llm_error(error: LLMAPIError) -> ServiceChatError:
    match error:
        case LLMAuthenticationError():
            return ServiceAuthenticationError(str(error))
        case LLMRateLimitError():
            return ServiceRateLimitError(str(error))
        case LLMConnectionError():
            return ServiceConnectionError(str(error))
        case _:
            return ServiceProviderError(str(error))


class ChatService:
    """Chat streaming adapter for the in-process service."""

    def __init__(self, agent) -> None:
        self._agent = agent

    async def chat(self, message: str) -> AsyncIterator[StreamEvent]:
        try:
            async for llm_event in self._agent.run(message):
                yield map_llm_event_to_stream_event(llm_event)
        except LLMAPIError as error:
            raise _translate_llm_error(error) from error
