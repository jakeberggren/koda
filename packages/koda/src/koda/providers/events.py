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
    tool_name: str
    call_id: str


@dataclass(frozen=True, slots=True)
class ProviderToolCompleted:
    tool_name: str
    call_id: str
    display: str | None = None
    is_error: bool = False


ProviderEvent = (
    TextDelta | ToolCallRequested | ToolCallResult | ProviderToolStarted | ProviderToolCompleted
)
