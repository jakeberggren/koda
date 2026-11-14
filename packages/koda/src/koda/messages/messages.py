from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Literal

from koda.tools import ToolCall, ToolResult


class MessageRole(StrEnum):
    USER = auto()
    ASSISTANT = auto()
    TOOL = auto()
    INTERRUPTION = auto()


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


@dataclass(frozen=True, slots=True, kw_only=True)
class UserMessage:
    content: str
    role: Literal[MessageRole.USER] = MessageRole.USER


@dataclass(frozen=True, slots=True, kw_only=True)
class InterruptionMessage:
    """The user interrupted the response; the model is told so with ``content``."""

    content: str = "The user interrupted the response."
    role: Literal[MessageRole.INTERRUPTION] = MessageRole.INTERRUPTION


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantMessage:
    content: str = ""
    thinking_content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage | None = None
    role: Literal[MessageRole.ASSISTANT] = MessageRole.ASSISTANT


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolMessage:
    tool_name: str
    tool_result: ToolResult
    content: str = ""
    role: Literal[MessageRole.TOOL] = MessageRole.TOOL


# Everything a conversation holds; ``role`` tells them apart once saved.
Message = UserMessage | AssistantMessage | ToolMessage | InterruptionMessage
