from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from koda.llm.models import ThinkingOptionId
from koda.messages import AssistantMessage, Message, TokenUsage
from koda.tools import ToolCall, ToolDefinition, ToolResult

_MAX_TOP_LOGPROBS = 20


class LLMRequestOptionsError(Exception):
    """Raised when LLM request options are invalid."""

    def __init__(self, field_name: str, value: object, expected: str) -> None:
        super().__init__(f"Invalid `{field_name}`: expected {expected}, got {value}.")
        self.field_name = field_name
        self.value = value
        self.expected = expected


@dataclass(frozen=True, slots=True)
class LLMRequestOptions:
    max_output_tokens: int | None = None
    max_tool_calls: int | None = None
    extended_prompt_retention: bool = False
    parallel_tool_calls: bool = True
    web_search: bool = False
    temperature: float | None = None
    thinking: ThinkingOptionId = "none"
    top_logprobs: int | None = None
    top_p: float | None = None
    truncation: Literal["auto", "disabled"] = "disabled"

    def __post_init__(self) -> None:
        if self.top_logprobs is not None and not 0 <= self.top_logprobs <= _MAX_TOP_LOGPROBS:
            raise LLMRequestOptionsError(
                field_name="top_logprobs",
                value=self.top_logprobs,
                expected=f"an integer between 0 and {_MAX_TOP_LOGPROBS}",
            )
        if self.top_p is not None and not 0 <= self.top_p <= 1:
            raise LLMRequestOptionsError(
                field_name="top_p",
                value=self.top_p,
                expected="a float between 0 and 1",
            )
        if self.temperature is not None and not 0 <= self.temperature <= 1:
            raise LLMRequestOptionsError(
                field_name="temperature",
                value=self.temperature,
                expected="a float between 0 and 1",
            )


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: Sequence[Message]
    instructions: str | None = None
    tools: Sequence[ToolDefinition] | None = None
    options: LLMRequestOptions = field(default_factory=LLMRequestOptions)


@dataclass(frozen=True, slots=True)
class LLMResponse[T]:
    output: T
    usage: TokenUsage | None = None


# Streaming events


@dataclass(frozen=True, slots=True)
class LLMTextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class LLMThinkingDelta:
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
    | LLMThinkingDelta
    | LLMToolCallRequested
    | LLMToolCallResult
    | LLMToolStarted
    | LLMToolCompleted
    | LLMResponseCompleted
)
