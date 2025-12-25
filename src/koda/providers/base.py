from collections.abc import AsyncIterator
from typing import Protocol

from koda.core import message
from koda.providers.adapter import ProviderAdapter
from koda.providers.events import ProviderEvent
from koda.tools.base import ToolDefinition


class Provider(Protocol):
    """Protocol for AI providers."""

    adapter: ProviderAdapter
    """Adapter for converting to/from provider-specific formats."""

    def stream(
        self, messages: list[message.Message], tools: list[ToolDefinition] | None = None
    ) -> AsyncIterator[ProviderEvent]: ...
