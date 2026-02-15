from pydantic import BaseModel, ConfigDict

from koda_common.contracts.tools import ToolCall, ToolResult


class EventBase(BaseModel):
    # Contract models are immutable and strict at the boundary.
    model_config = ConfigDict(frozen=True, extra="forbid")


class TextDelta(EventBase):
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


StreamEvent = (
    TextDelta | ToolCallRequested | ToolCallResult | ProviderToolStarted | ProviderToolCompleted
)
