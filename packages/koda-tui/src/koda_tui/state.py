from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from koda.llm import ModelDefinition, ProviderDefinition, ThinkingOption
from koda.messages import TokenUsage
from koda.tools import ToolCall, ToolOutput
from koda_service import ServiceStatus


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
    service_status: ServiceStatus
    warnings: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    responding: bool = False  # Whether a response is in flight.
    pending_inputs: list[PendingInput] = field(default_factory=list)  # Steers first.
    active_model: ModelDefinition | None = None
    configured_providers: list[ProviderDefinition] = field(default_factory=list)
    thinking: ThinkingOption = field(default_factory=ThinkingOption.none)
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
