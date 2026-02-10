from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from koda.messages import Message
from koda.tools import ToolDefinition

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.messages import Message
    from koda.providers.events import ProviderEvent
    from koda.tools import ToolCall, ToolDefinition


class ProviderAdapter(Protocol):
    """Protocol for converting between internal and provider-specific formats."""

    def adapt_messages(self, messages: list[Message]) -> Any:
        """Convert internal messages to provider-specific format."""
        ...

    def adapt_tools(self, tools: list[ToolDefinition] | None) -> Any:
        """Convert tool definitions to provider-specific format."""
        ...

    def parse_tool_calls(self, response: Any) -> list[ToolCall]:
        """Parse tool calls from provider-specific response format."""
        ...


class Provider(Protocol):
    """Protocol for AI providers."""

    adapter: ProviderAdapter
    """Adapter for converting to/from provider-specific formats."""

    def reset_state(self) -> None:
        """Reset provider-specific conversational state (e.g., response threading).

        Called when the active session changes. Providers that do not maintain
        conversational state can leave this as a no-op.
        """
        ...

    def stream(
        self,
        messages: list[Message],
        system_message: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ProviderEvent]: ...
