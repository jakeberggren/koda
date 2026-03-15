from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from koda_service.types.tools import ToolCall, ToolResult


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    role: MessageRole = Field(...)
    content: str = Field(default="")


class UserMessage(Message):
    role: Literal[MessageRole.USER] = Field(default=MessageRole.USER, frozen=True)


class AssistantMessage(Message):
    role: Literal[MessageRole.ASSISTANT] = Field(default=MessageRole.ASSISTANT, frozen=True)
    thinking_content: str = Field(default="")
    tool_calls: list[ToolCall] = Field(default_factory=list)


class SystemMessage(Message):
    role: Literal[MessageRole.SYSTEM] = Field(default=MessageRole.SYSTEM, frozen=True)


class ToolMessage(Message):
    role: Literal[MessageRole.TOOL] = Field(default=MessageRole.TOOL, frozen=True)
    tool_name: str = Field()
    tool_result: ToolResult = Field()
