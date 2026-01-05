from collections.abc import AsyncIterator
from typing import Protocol

from koda.providers.events import ProviderEvent


class Backend(Protocol):
    """Protocol for TUI backends."""

    def chat(self, message: str) -> AsyncIterator[ProviderEvent]:
        """Send a message and stream response events."""
        ...
