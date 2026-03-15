from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    call_id: str


class ToolOutput(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)
    display: str | None = None
    is_error: bool = False
    error_message: str | None = None


class ToolResult(BaseModel):
    output: ToolOutput
    call_id: str
