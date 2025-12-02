"""Base provider interface and abstractions."""

from collections.abc import AsyncIterator
from typing import Protocol

from agents.core.message import Message


class Provider(Protocol):
    """Protocol defining the provider interface.

    Any class that implements these methods will satisfy this protocol.
    No explicit inheritance is required - structural typing is used.
    """

    async def chat(self, messages: list[Message]) -> str:
        """Send messages to the provider and get a response.

        Args:
            messages: List of messages in the conversation.

        Returns:
            The assistant's response as a string.
        """
        ...

    def stream(self, messages: list[Message]) -> AsyncIterator[str]:
        """Stream a response from the provider.

        Args:
            messages: List of messages in the conversation.

        Yields:
            Text chunks as they are generated.
        """
        ...
