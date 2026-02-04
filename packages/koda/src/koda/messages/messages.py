from enum import StrEnum, auto

from pydantic import BaseModel, Field

from koda.tools import ToolCall, ToolResult


class MessageRole(StrEnum):
    USER = auto()
    ASSISTANT = auto()
    SYSTEM = auto()
    TOOL = auto()


class Message(BaseModel):
    role: MessageRole = Field(...)
    content: str = Field(default="")


class UserMessage(Message):
    role: MessageRole = Field(default=MessageRole.USER, frozen=True)


class AssistantMessage(Message):
    role: MessageRole = Field(default=MessageRole.ASSISTANT, frozen=True)
    tool_calls: list[ToolCall] = Field(default_factory=list)


class SystemMessage(Message):
    role: MessageRole = Field(default=MessageRole.SYSTEM, frozen=True)


class ToolMessage(Message):
    role: MessageRole = Field(default=MessageRole.TOOL, frozen=True)
    tool_name: str = Field()
    tool_result: ToolResult = Field()
