from enum import StrEnum, auto
from typing import Literal

from pydantic import BaseModel, Field

from koda.tools import ToolCall, ToolResult


class MessageRole(StrEnum):
    USER = auto()
    ASSISTANT = auto()
    TOOL = auto()


class Message(BaseModel):
    role: MessageRole = Field(...)
    content: str = Field(default="")


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    total_tokens: int | None = None


class UserMessage(Message):
    role: Literal[MessageRole.USER] = Field(default=MessageRole.USER, frozen=True)


class AssistantMessage(Message):
    role: Literal[MessageRole.ASSISTANT] = Field(default=MessageRole.ASSISTANT, frozen=True)
    thinking_content: str = Field(default="")
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage | None = None


class ToolMessage(Message):
    role: Literal[MessageRole.TOOL] = Field(default=MessageRole.TOOL, frozen=True)
    tool_name: str = Field()
    tool_result: ToolResult = Field()
