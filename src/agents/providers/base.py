from collections.abc import AsyncIterator
from typing import Protocol

from agents.core import message


class Provider(Protocol):
    async def chat(self, messages: list[message.Message]) -> str: ...

    """Generate a response from the provider."""

    def stream(self, messages: list[message.Message]) -> AsyncIterator[str]: ...

    """Stream the response from the provider."""
