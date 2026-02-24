from collections.abc import Sequence
from dataclasses import dataclass

from koda.messages import AssistantMessage, Message
from koda.tools import ToolCall, ToolDefinition, ToolResult


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: Sequence[Message]
    system_message: str | None = None
    tools: Sequence[ToolDefinition] | None = None


@dataclass(frozen=True, slots=True)
class LLMTokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse[T]:
    output: T
    usage: LLMTokenUsage | None = None


# Streaming events


@dataclass(frozen=True, slots=True)
class LLMTextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class LLMToolCallRequested:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class LLMToolCallResult:
    tool_name: str
    result: ToolResult


@dataclass(frozen=True, slots=True)
class LLMToolStarted:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class LLMToolCompleted:
    tool_name: str
    result: ToolResult


@dataclass(frozen=True, slots=True)
class LLMResponseCompleted:
    response: LLMResponse[AssistantMessage]


LLMEvent = (
    LLMTextDelta
    | LLMToolCallRequested
    | LLMToolCallResult
    | LLMToolStarted
    | LLMToolCompleted
    | LLMResponseCompleted
)
