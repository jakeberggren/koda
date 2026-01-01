from typing import Any, Protocol

from koda.messages import Message
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
