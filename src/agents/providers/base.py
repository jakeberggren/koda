from collections.abc import AsyncIterator
from typing import Protocol

from agents.core.message import Message


class Provider(Protocol):
    async def chat(self, messages: list[Message]) -> str: ...

    """Generate a response from the provider."""

    def stream(self, messages: list[Message]) -> AsyncIterator[str]: ...

    """Stream the response from the provider."""
