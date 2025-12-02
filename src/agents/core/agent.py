"""Core agent implementation."""

from collections.abc import AsyncIterator

from agents.core.message import AssistantMessage, Message, SystemMessage, UserMessage
from agents.providers import Provider
from agents.utils.exceptions import ProviderValidationError


class Agent:
    """Simple, composable agent that manages conversation state.

    The Agent class wraps a Provider and manages conversation history,
    making it easy to have multi-turn conversations with a simple API.

    Args:
        provider: The provider to use for generating responses.
        system_message: Optional system message to set the agent's behavior.

    Example:
        ```python
        agent = Agent(provider=openai_provider, system_message="You are a helpful assistant.")
        response = await agent.chat("Hello!")
        ```
    """

    def __init__(self, provider: Provider, system_message: str | None = None) -> None:
        """Initialize the agent with a provider and optional system message.

        Args:
            provider: The provider to use for generating responses.
            system_message: Optional system message to set the agent's behavior.

        Raises:
            ProviderValidationError: If provider is None.
        """
        if provider is None:
            raise ProviderValidationError("Provider cannot be None")

        self.provider: Provider = provider
        self.system_message: str | None = system_message
        self._history: list[Message] = []

        # Add system message to history if provided
        if system_message:
            self._history.append(SystemMessage(content=system_message))

    async def chat(self, message: str) -> str:
        """Send a message and get a response.

        The message is added to conversation history, and the response
        is also stored in history for context in future messages.

        Args:
            message: The user's message.

        Returns:
            The assistant's response as a string.

        Raises:
            ProviderValidationError: If message is empty.
            ProviderError: If the provider encounters an error.
        """
        if not message or not message.strip():
            raise ProviderValidationError("Message cannot be empty")

        # Create user message and add to history
        user_message = UserMessage(content=message.strip())
        self._history.append(user_message)

        # Build message list for provider
        messages = self._build_messages()

        # Get response from provider
        response_text = await self.provider.chat(messages)

        # Create assistant message and add to history
        assistant_message = AssistantMessage(content=response_text)
        self._history.append(assistant_message)

        return response_text

    async def stream(self, message: str) -> AsyncIterator[str]:
        """Stream a response from the agent.

        The message is added to conversation history. The response chunks
        are streamed, and the complete response is stored in history
        when streaming completes.

        Args:
            message: The user's message.

        Yields:
            Text chunks as they are generated.

        Raises:
            ProviderValidationError: If message is empty.
            ProviderError: If the provider encounters an error.
        """
        if not message or not message.strip():
            raise ProviderValidationError("Message cannot be empty")

        # Create user message and add to history
        user_message = UserMessage(content=message.strip())
        self._history.append(user_message)

        # Build message list for provider
        messages = self._build_messages()

        # Stream response from provider
        stream = self.provider.stream(messages)
        response_chunks: list[str] = []
        async for chunk in stream:
            response_chunks.append(chunk)
            yield chunk

        # Create assistant message and add to history
        response_text = "".join(response_chunks)
        assistant_message = AssistantMessage(content=response_text)
        self._history.append(assistant_message)

    def add_message(self, message: Message) -> None:
        """Manually add a message to conversation history.

        This is useful for programmatically building conversation history
        or adding messages from external sources.

        Args:
            message: The message to add to history.
        """
        self._history.append(message)

    def get_history(self) -> list[Message]:
        """Get a copy of the conversation history.

        Returns:
            A copy of the conversation history (read-only).
        """
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear the conversation history.

        Note: This does not reset the provider's internal state.
        Use reset() to reset both history and provider state.
        """
        # Preserve system message if it exists
        system_msg = None
        if self._history and self._history[0].role.value == "system":
            system_msg = self._history[0]

        self._history.clear()

        # Restore system message if it existed
        if system_msg:
            self._history.append(system_msg)

    def reset(self) -> None:
        """Reset the agent state.

        Clears conversation history and resets the provider's internal state
        (if the provider supports it).
        """
        self.clear_history()

        # Reset provider state if it has a reset_state method
        reset_state = getattr(self.provider, "reset_state", None)
        if reset_state is not None and callable(reset_state):
            reset_state()

    def _build_messages(self) -> list[Message]:
        """Build the message list for the provider.

        Returns:
            A copy of the conversation history to send to the provider.
        """
        return self._history.copy()
