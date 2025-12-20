from collections.abc import AsyncIterator
from typing import Protocol

from koda.core import message
from koda.providers.events import ProviderEvent
from koda.tools.base import ToolCall, ToolDefinition


class ToolCallResponse:
    """Response containing tool calls instead of text."""

    def __init__(self, tool_calls: list[ToolCall]) -> None:
        self.tool_calls = tool_calls


class Provider(Protocol):
    def stream(
        self, messages: list[message.Message], tools: list[ToolDefinition] | None = None
    ) -> AsyncIterator[ProviderEvent]: ...
