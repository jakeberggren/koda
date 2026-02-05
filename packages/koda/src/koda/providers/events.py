from dataclasses import dataclass

from koda.tools import ToolCall, ToolResult


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallRequested:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    tool_name: str
    result: ToolResult


@dataclass(frozen=True, slots=True)
class ProviderToolStarted:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class ProviderToolCompleted:
    tool_name: str
    result: ToolResult


ProviderEvent = (
    TextDelta | ToolCallRequested | ToolCallResult | ProviderToolStarted | ProviderToolCompleted
)
