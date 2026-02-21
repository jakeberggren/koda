from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from koda.messages import Message
from koda.tools import ToolDefinition

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from koda.messages import Message
    from koda.providers.events import ProviderEvent
    from koda.tools import ToolCall, ToolDefinition


class ProviderAdapter[MessagesT, ToolsT, ResponseT](Protocol):
    """Protocol for converting between internal and provider-specific formats."""

    def adapt_messages(self, messages: Sequence[Message]) -> MessagesT:
        """Convert internal messages to provider-specific format."""
        ...

    def adapt_tools(self, tools: list[ToolDefinition] | None) -> ToolsT:
        """Convert tool definitions to provider-specific format."""
        ...

    def parse_tool_calls(self, response: ResponseT) -> list[ToolCall]:
        """Parse tool calls from provider-specific response format."""
        ...


class Provider[AdapterT: ProviderAdapter[Any, Any, Any]](Protocol):
    """Protocol for AI providers."""

    adapter: AdapterT
    """Adapter for converting to/from provider-specific formats."""

    def stream(
        self,
        messages: Sequence[Message],
        system_message: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ProviderEvent]: ...
