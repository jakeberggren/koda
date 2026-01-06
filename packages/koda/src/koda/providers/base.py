from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.messages import Message
    from koda.providers.adapter import ProviderAdapter
    from koda.providers.events import ProviderEvent
    from koda.tools import ToolDefinition


class Provider(Protocol):
    """Protocol for AI providers."""

    adapter: ProviderAdapter
    """Adapter for converting to/from provider-specific formats."""

    def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ProviderEvent]: ...
