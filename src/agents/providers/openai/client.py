"""OpenAI provider implementation using the Responses API."""

from collections.abc import AsyncIterator

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from agents.core.message import Message, MessageRole
from agents.providers.base import Provider
from agents.utils.exceptions import (
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderValidationError,
)


class OpenAIProvider(Provider):
    """OpenAI provider implementation using the Responses API.

    Implements the Provider protocol. Uses OpenAI's Responses API which
    is stateful and designed for agentic workflows.

    Args:
        api_key: OpenAI API key.
        model: Model to use (default: "gpt-5.1").
        base_url: Optional base URL for custom endpoints.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.1",
        base_url: str | None = None,
    ) -> None:
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model to use (default: "gpt-5.1").
            base_url: Optional base URL for custom endpoints.

        Raises:
            ProviderValidationError: If API key is empty.
        """
        if not api_key or not api_key.strip():
            raise ProviderValidationError("OpenAI API key cannot be empty")

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model: str = model
        self._last_response_id: str | None = None

    async def chat(self, messages: list[Message]) -> str:
        """Send messages and get a response.

        Args:
            messages: List of messages in the conversation.

        Returns:
            The assistant's response as a string.

        Raises:
            ProviderValidationError: If messages list is empty.
            ProviderRateLimitError: If rate limit is exceeded.
            ProviderAuthenticationError: If authentication fails.
            ProviderAPIError: If an API error occurs.
            ProviderResponseError: If response is empty or invalid.
        """
        if not messages:
            raise ProviderValidationError("Messages list cannot be empty")

        input_text: str = self._messages_to_input(messages)

        try:
            response = await self.client.responses.create(
                model=self.model,
                input=input_text,
                previous_response_id=self._last_response_id,
            )
        except RateLimitError as e:
            raise ProviderRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except AuthenticationError as e:
            raise ProviderAuthenticationError(f"OpenAI authentication failed: {e}") from e
        except (APIConnectionError, APITimeoutError) as e:
            raise ProviderAPIError(f"OpenAI connection error: {e}") from e
        except APIError as e:
            raise ProviderAPIError(f"OpenAI API error: {e}") from e

        # Store response ID for stateful conversations
        if response.id:
            self._last_response_id = response.id

        if not response.output or len(response.output) == 0:
            raise ProviderResponseError("Received empty output from OpenAI API")
        output = response.output[0]
        if not output.content or len(output.content) == 0:
            raise ProviderResponseError("Received empty content from OpenAI API")
        content = output.content[0]
        if not hasattr(content, "text") or not content.text:
            raise ProviderResponseError("Received response without text content from OpenAI API")
        return content.text

    async def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a response from the provider.

        Args:
            messages: List of messages in the conversation.

        Yields:
            Text chunks as they are generated.

        Raises:
            ProviderValidationError: If messages list is empty.
            ProviderRateLimitError: If rate limit is exceeded.
            ProviderAuthenticationError: If authentication fails.
            ProviderAPIError: If an API error occurs.
        """
        if not messages:
            raise ProviderValidationError("Messages list cannot be empty")

        input_text = self._messages_to_input(messages)

        try:
            stream = await self.client.responses.create(
                model=self.model,
                input=input_text,
                previous_response_id=self._last_response_id,
                stream=True,
            )
        except RateLimitError as e:
            raise ProviderRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except AuthenticationError as e:
            raise ProviderAuthenticationError(f"OpenAI authentication failed: {e}") from e
        except (APIConnectionError, APITimeoutError) as e:
            raise ProviderAPIError(f"OpenAI connection error: {e}") from e
        except APIError as e:
            raise ProviderAPIError(f"OpenAI API error: {e}") from e

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

    def _messages_to_input(self, messages: list[Message]) -> str:
        """Convert a list of messages to a single input string.

        Args:
            messages: List of messages to convert.

        Returns:
            Combined input string for the Responses API.
        """
        parts = []
        for msg in messages:
            role_prefix: str = f"{msg.role.value.upper()}: " if msg.role != MessageRole.USER else ""
            parts.append(f"{role_prefix}{msg.content}")

        return "\n\n".join(parts)

    def reset_state(self) -> None:
        """Reset the conversation state.

        Clears the stored response ID, effectively starting a new conversation.
        """
        self._last_response_id = None
