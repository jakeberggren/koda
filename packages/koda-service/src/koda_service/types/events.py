from pydantic import BaseModel, ConfigDict

from koda_service.types.messages import AssistantMessage
from koda_service.types.tools import ToolCall, ToolResult


class EventBase(BaseModel):
    # Contract models are immutable and strict at the boundary.
    model_config = ConfigDict(frozen=True, extra="forbid")


class TextDelta(EventBase):
    text: str


class ThinkingDelta(EventBase):
    text: str


class ToolCallRequested(EventBase):
    call: ToolCall


class ToolCallResult(EventBase):
    tool_name: str
    result: ToolResult


class ProviderToolStarted(EventBase):
    call: ToolCall


class ProviderToolCompleted(EventBase):
    tool_name: str
    result: ToolResult


class TokenUsage(EventBase):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    total_tokens: int | None = None


class ResponseCompleted(EventBase):
    output: AssistantMessage
    usage: TokenUsage | None = None


StreamEvent = (
    TextDelta
    | ThinkingDelta
    | ToolCallRequested
    | ToolCallResult
    | ProviderToolStarted
    | ProviderToolCompleted
    | ResponseCompleted
)
