from collections.abc import AsyncIterator, Iterator

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
)

from koda.messages import Message
from koda.providers import Provider, exceptions
from koda.providers.events import ProviderEvent, TextDelta, ToolCallRequested
from koda.providers.openai import OpenAIAdapter
from koda.tools import ToolDefinition
from koda_common.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(Provider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        base_url: str | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            logger.error("empty_api_key", provider="OpenAI")
            raise exceptions.EmptyApiKeyError("OpenAI")

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model: str = model
        self.adapter: OpenAIAdapter = OpenAIAdapter()
        self._last_response_id: str | None = None
        logger.info("openai_provider_initialized", model=model, has_base_url=base_url is not None)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        if not messages:
            logger.warning("stream_called_with_empty_messages")
            raise exceptions.EmptyMessagesListError

        logger.info("stream_started", message_count=len(messages))
        openai_input = self.adapter.adapt_messages(messages)
        openai_tools = self.adapter.adapt_tools(tools)

        try:
            stream = await self.client.responses.create(
                model=self.model,
                previous_response_id=self._last_response_id,
                stream=True,
                tools=openai_tools,
                input=openai_input,
            )
            async for event in stream:
                for processed_event in self._process_event(event):
                    yield processed_event
            logger.info("stream_completed")
        except Exception as e:
            self._handle_provider_exceptions(e)

    def reset_state(self) -> None:
        self._last_response_id = None

    def _process_event(
        self,
        event: ResponseStreamEvent,
    ) -> Iterator[ProviderEvent]:
        if isinstance(event, ResponseTextDeltaEvent):
            yield TextDelta(text=event.delta)
        elif isinstance(event, ResponseCompletedEvent):
            self._last_response_id = event.response.id
            tool_calls = self.adapter.parse_tool_calls(event.response)
            for call in tool_calls:
                yield ToolCallRequested(call=call)

    def _handle_provider_exceptions(self, e: Exception) -> None:
        if isinstance(e, RateLimitError):
            logger.error("provider_rate_limit_error", provider="OpenAI")
            raise exceptions.ProviderRateLimitError("OpenAI", e) from e
        if isinstance(e, AuthenticationError):
            logger.error("provider_authentication_error", provider="OpenAI")
            raise exceptions.ProviderAuthenticationError("OpenAI", e) from e
        if isinstance(e, (APIConnectionError, APITimeoutError)):
            logger.error("provider_connection_error", provider="OpenAI", error=repr(e))
            raise exceptions.ProviderConnectionError("OpenAI", e) from e
        if isinstance(e, APIError):
            logger.error("provider_api_error", provider="OpenAI", error=repr(e))
            raise exceptions.ProviderAPIError("OpenAI", e) from e
        logger.error("provider_unknown_error", provider="OpenAI", error=repr(e))
        raise exceptions.ProviderAPIError("OpenAI", e) from e
