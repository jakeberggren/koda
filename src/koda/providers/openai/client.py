from collections.abc import AsyncIterator

from langfuse import observe
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from koda.core import message
from koda.providers import base as providers_base
from koda.utils import exceptions


class OpenAIProvider(providers_base.Provider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.1",
        base_url: str | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise exceptions.ProviderValidationError("OpenAI API key cannot be empty")

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model: str = model
        self._last_response_id: str | None = None

    @observe(name="openai.chat")
    async def chat(self, messages: list[message.Message]) -> str:
        if not messages:
            raise exceptions.ProviderValidationError("Messages list cannot be empty")

        input_text: str = self._messages_to_input(messages)

        try:
            response = await self.client.responses.create(
                model=self.model,
                input=input_text,
                previous_response_id=self._last_response_id,
            )
        except RateLimitError as e:
            raise exceptions.ProviderRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except AuthenticationError as e:
            auth_error_msg = f"OpenAI authentication failed: {e}"
            raise exceptions.ProviderAuthenticationError(auth_error_msg) from e
        except (APIConnectionError, APITimeoutError) as e:
            raise exceptions.ProviderAPIError(f"OpenAI connection error: {e}") from e
        except APIError as e:
            raise exceptions.ProviderAPIError(f"OpenAI API error: {e}") from e

        # Store response ID for stateful conversations
        if response.id:
            self._last_response_id = response.id

        if not response.output or len(response.output) == 0:
            raise exceptions.ProviderResponseError("Received empty output from OpenAI API")
        output = response.output[0]
        if not output.content or len(output.content) == 0:
            raise exceptions.ProviderResponseError("Received empty content from OpenAI API")
        content = output.content[0]
        if not hasattr(content, "text") or not content.text:
            raise exceptions.ProviderResponseError(
                "Received response without text content from OpenAI API"
            )
        return content.text

    @observe(name="openai.stream")
    async def stream(self, messages: list[message.Message]) -> AsyncIterator[str]:
        if not messages:
            raise exceptions.ProviderValidationError("Messages list cannot be empty")

        input_text = self._messages_to_input(messages)

        try:
            stream = await self.client.responses.create(
                model=self.model,
                input=input_text,
                previous_response_id=self._last_response_id,
                stream=True,
            )
        except RateLimitError as e:
            raise exceptions.ProviderRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except AuthenticationError as e:
            auth_error_msg = f"OpenAI authentication failed: {e}"
            raise exceptions.ProviderAuthenticationError(auth_error_msg) from e
        except (APIConnectionError, APITimeoutError) as e:
            raise exceptions.ProviderAPIError(f"OpenAI connection error: {e}") from e
        except APIError as e:
            raise exceptions.ProviderAPIError(f"OpenAI API error: {e}") from e

        async for event in stream:
            # Responses API streaming events have a 'type' field
            # Check for text delta events
            event_type = getattr(event, "type", None)
            delta_text = None

            if event_type:
                event_type_lower = event_type.lower()

                # Only process delta events - skip full text/output events to prevent duplication
                # Delta events contain incremental text chunks
                is_delta_event = "delta" in event_type_lower

                if is_delta_event:
                    # Try different possible locations for delta text
                    # Stop as soon as we find text in any location to avoid duplication
                    # Check event.data.delta first
                    if hasattr(event, "data"):
                        data = event.data
                        if hasattr(data, "delta") and data.delta:
                            delta_text = data.delta
                        elif hasattr(data, "text") and data.text:
                            delta_text = data.text

                    # Check event.delta directly (only if not found in data)
                    if not delta_text and hasattr(event, "delta") and event.delta:
                        delta_text = event.delta

                    # Check event.text (only if not found elsewhere)
                    if not delta_text and hasattr(event, "text") and event.text:
                        delta_text = event.text

                # Handle completed events to get response ID (but don't yield text from them)
                if "completed" in event_type_lower and hasattr(event, "id"):
                    event_id = getattr(event, "id", None)
                    if event_id is not None and isinstance(event_id, str):
                        self._last_response_id = event_id
                    # Skip text extraction for completed events
                    continue

            # Yield the delta text only once per event (only for delta events)
            if delta_text:
                yield str(delta_text)

    def _messages_to_input(self, messages: list[message.Message]) -> str:
        parts = []
        for msg in messages:
            role_prefix: str = (
                f"{msg.role.value.upper()}: " if msg.role != message.MessageRole.USER else ""
            )
            parts.append(f"{role_prefix}{msg.content}")

        return "\n\n".join(parts)

    def reset_state(self) -> None:
        self._last_response_id = None
