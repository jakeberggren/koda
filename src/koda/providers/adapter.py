from abc import ABC, abstractmethod
from typing import Any

from koda.core import message
from koda.tools.base import ToolCall, ToolDefinition


class ProviderAdapter(ABC):
    """Adapter interface for converting between internal and provider-specific formats."""

    @abstractmethod
    def adapt_messages(self, messages: list[message.Message]) -> Any:
        """Convert internal messages to provider-specific format."""
        ...

    @abstractmethod
    def adapt_tool_definition(self, tool: ToolDefinition) -> Any:
        """Convert internal tool definition to provider-specific format."""
        ...

    @abstractmethod
    def adapt_tool_definitions(self, tools: list[ToolDefinition] | None) -> Any:
        """Convert list of tool definitions to provider-specific format."""
        ...

    @abstractmethod
    def parse_tool_calls(self, response: Any) -> list[ToolCall]:
        """Parse tool calls from provider-specific response format."""
        ...
