from collections.abc import AsyncIterator
from typing import Protocol

from koda.providers.events import ProviderEvent


class Client(Protocol):
    """Protocol for TUI clients."""

    def chat(self, message: str) -> AsyncIterator[ProviderEvent]:
        """Send a message and stream response events."""
        ...
