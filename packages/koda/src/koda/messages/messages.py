from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    total_tokens: int | None = None

    def context_window_percentage(self, context_window: int | None) -> int | None:
        """Return input token usage as a percentage of a context window."""
        if context_window is None or context_window <= 0 or self.input_tokens is None:
            return None
        return round((self.input_tokens / context_window) * 100)


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
