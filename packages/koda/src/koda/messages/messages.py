from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Literal

# What JSON holds: what the model sends a tool, and what a tool sends back.
type JsonValue = str | int | float | bool | Sequence[JsonValue] | Mapping[str, JsonValue] | None


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
class ToolCall:
    """The model asking for a tool to run with ``arguments``; its result answers ``call_id``."""

    tool_name: str
    arguments: Mapping[str, JsonValue]
    call_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolOutput:
    """What a tool sends back: ``content`` for the model, ``display`` for people."""

    content: Mapping[str, JsonValue] = field(default_factory=dict)
    display: str | None = None
    is_error: bool = False
    error_message: str | None = None

    @classmethod
    def failure(cls, message: str) -> ToolOutput:
        """An output saying the tool couldn't do what was asked, and why."""
        return cls(is_error=True, error_message=message)


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
    """A tool's ``output``, answering the call with ``call_id``."""

    tool_name: str
    call_id: str
    output: ToolOutput
    role: Literal[MessageRole.TOOL] = MessageRole.TOOL


# Everything a conversation holds; ``role`` tells them apart once saved.
Message = UserMessage | AssistantMessage | ToolMessage | InterruptionMessage
