from enum import Enum

from pydantic import BaseModel, Field

from koda.tools.base import ToolCall, ToolResult


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class Message(BaseModel):
    role: MessageRole = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")

    def __str__(self) -> str:
        return f"{self.role.value}: {self.content}"


class UserMessage(Message):
    role: MessageRole = Field(default=MessageRole.USER, frozen=True)


class AssistantMessage(Message):
    role: MessageRole = Field(default=MessageRole.ASSISTANT, frozen=True)


class SystemMessage(Message):
    role: MessageRole = Field(default=MessageRole.SYSTEM, frozen=True)


class ToolCallMessage(Message):
    """Message containing tool call requests from the assistant."""

    role: MessageRole = Field(default=MessageRole.TOOL_CALL, frozen=True)
    tool_calls: list[ToolCall] = Field(..., description="List of tool calls to execute")
    content: str = Field(default="", frozen=True)

    def __str__(self) -> str:
        calls_str = ", ".join(f"{call.tool_name}({call.call_id})" for call in self.tool_calls)
        return f"{self.role.value}: {calls_str}"


class ToolResultMessage(Message):
    """Message containing tool execution results."""

    role: MessageRole = Field(default=MessageRole.TOOL_RESULT, frozen=True)
    tool_name: str = Field(..., description="Name of the tool that was executed")
    result: ToolResult = Field(..., description="Result of tool execution")
    call_id: str | None = Field(default=None, description="ID matching the tool call")
    content: str = Field(default="", frozen=True)

    def __str__(self) -> str:
        result_str = str(self.result.content) if self.result.content is not None else "None"
        return f"{self.role.value}: {self.tool_name} -> {result_str}"
