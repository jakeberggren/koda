from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from koda.llm import Model, Provider, ThinkingOption
from koda.sessions import Session
from koda_tui.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm import ThinkingOptionId
    from koda.messages import TokenUsage
    from koda.tools import ToolCall, ToolOutput


class ResponsePhase(Enum):
    """Current phase of an in-flight response."""

    IDLE = auto()
    WORKING = auto()
    THINKING = auto()
    RESPONDING = auto()
    TOOLS = auto()


@dataclass(frozen=True, slots=True)
class UserMessage:
    text: str


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    text: str
    thinking: str = ""


@dataclass(frozen=True, slots=True)
class ToolMessage:
    call: ToolCall
    result: ToolOutput | None = None  # None while the tool runs.


@dataclass(frozen=True, slots=True)
class ErrorMessage:
    """A response that failed: what went wrong, and what to do about it if known."""

    summary: str
    detail: str | None = None


type Message = UserMessage | AssistantMessage | ToolMessage | ErrorMessage


@dataclass(frozen=True, slots=True)
class PendingInput:
    """A message waiting to be sent: queued behind the response, or steering into it."""

    text: str
    steer: bool = False


@dataclass(frozen=True, slots=True)
class Usage:
    """Token usage: the latest response's, which shows how full the context is, and the
    session's total."""

    latest: TokenUsage
    total: TokenUsage


@dataclass
class AppState:
    """Shared application state as single source of truth for the UI."""

    workspace: Path
    settings: Settings = field(default_factory=Settings)
    session: Session = field(default_factory=Session)  # The conversation on screen.
    issue: str | None = None  # What stops Koda from responding; None when it can.
    warnings: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    responding: bool = False  # Whether a response is in flight.
    pending_inputs: list[PendingInput] = field(default_factory=list)  # Steers first.
    active_model: Model | None = None
    configured_providers: list[Provider] = field(default_factory=list)
    usage: Usage | None = None
    exit_requested: bool = False

    @property
    def response_phase(self) -> ResponsePhase:
        """What the response in flight is doing: running tools first, then replying, then
        thinking; working before anything streams."""
        if not self.responding:
            return ResponsePhase.IDLE
        if any(isinstance(m, ToolMessage) and m.result is None for m in self.response()):
            return ResponsePhase.TOOLS
        last = self.messages[-1]  # A response always follows a user message.
        if isinstance(last, AssistantMessage):
            return ResponsePhase.RESPONDING if last.text else ResponsePhase.THINKING
        return ResponsePhase.WORKING

    def response(self) -> list[Message]:
        """The messages of the latest response: everything after the last user message."""
        for index in reversed(range(len(self.messages))):
            if isinstance(self.messages[index], UserMessage):
                return self.messages[index + 1 :]
        return self.messages

    @property
    def context_window(self) -> int | None:
        return self.active_model.context_window if self.active_model else None

    @property
    def thinking_supported(self) -> bool:
        return self.active_model is not None and self.active_model.supports_thinking

    @property
    def thinking(self) -> ThinkingOption:
        """The thinking level the settings pick for the active model."""
        if self.active_model is None:
            return ThinkingOption.none()
        return self.active_model.resolve_thinking_option(self.settings.thinking)

    def next_thinking(self) -> ThinkingOptionId | None:
        """The active model's thinking level after the current one, wrapping around;
        None without a ready model that has any."""
        if self.issue is not None or self.active_model is None:
            return None
        options = [option.id for option in self.active_model.effective_thinking_options]
        if not options:
            return None
        index = options.index(self.thinking.id) if self.thinking.id in options else -1
        return options[(index + 1) % len(options)]
