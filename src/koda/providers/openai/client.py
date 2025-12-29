from collections.abc import AsyncIterator

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
    ResponseTextDeltaEvent,
)

from koda.core import message
from koda.providers.base import Provider
from koda.providers.events import TextDelta, ToolCallRequested
from koda.providers.openai.adapter import OpenAIAdapter
from koda.tools import ToolDefinition
from koda.utils import exceptions


class OpenAIProvider(Provider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        base_url: str | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise exceptions.ProviderValidationError("OpenAI API key cannot be empty")

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model: str = model
        self.adapter: OpenAIAdapter = OpenAIAdapter()
        self._last_response_id: str | None = None

    async def stream(
        self,
        messages: list[message.Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[TextDelta | ToolCallRequested]:
        if not messages:
            raise exceptions.ProviderValidationError("Messages list cannot be empty")

        # Use adapter to convert messages and tools
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
                if isinstance(event, ResponseTextDeltaEvent):
                    yield TextDelta(text=event.delta)
                elif isinstance(event, ResponseCompletedEvent):
                    self._last_response_id = event.response.id
                    tool_calls = self.adapter.parse_tool_calls(event.response)
                    for call in tool_calls:
                        yield ToolCallRequested(call=call)
        except RateLimitError as e:
            raise exceptions.ProviderRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except AuthenticationError as e:
            auth_error_msg = f"OpenAI authentication failed: {e}"
            raise exceptions.ProviderAuthenticationError(auth_error_msg) from e
        except (APIConnectionError, APITimeoutError) as e:
            raise exceptions.ProviderAPIError(f"OpenAI connection error: {e}") from e
        except APIError as e:
            raise exceptions.ProviderAPIError(f"OpenAI API error: {e}") from e

    def reset_state(self) -> None:
        self._last_response_id = None
