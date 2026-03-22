from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from koda_service.types import ThinkingOption, ToolCall


class MessageRole(Enum):
    """Role of a message in the chat history."""

    USER = auto()
    ASSISTANT = auto()
    TOOL = auto()


class ResponsePhase(Enum):
    """Current phase of an in-flight response."""

    IDLE = auto()
    WORKING = auto()
    RESPONDING = auto()
    TOOLS = auto()


@dataclass
class Message:
    """A single message in the chat history."""

    role: MessageRole
    content: str
    thinking_content: str = ""
    tool_call: ToolCall | None = None
    tool_running: bool = False
    tool_error: bool = False
    tool_result_display: str | None = None
    tool_error_message: str | None = None


@dataclass
class AppState:
    """Shared application state as single source of truth for the UI."""

    workspace_root: Path
    messages: list[Message] = field(default_factory=list)
    current_streaming_content: str = ""
    current_thinking_content: str = ""
    is_streaming: bool = False
    is_thinking: bool = False
    response_phase: ResponsePhase = ResponsePhase.IDLE
    active_tools: dict[str, ToolCall] = field(default_factory=dict)
    pending_inputs: list[str] = field(default_factory=list)
    model_name: str = ""
    provider_name: str = ""
    thinking: ThinkingOption = field(
        default_factory=lambda: ThinkingOption(id="none", label="none")
    )
    thinking_supported: bool = False
    show_scrollbar: bool = True
    queue_inputs: bool = True
    exit_requested: bool = False
    palette_open: bool = False

    def reset_conversation(self) -> None:
        """Clear all conversation and streaming state."""
        self.messages.clear()
        self.current_streaming_content = ""
        self.current_thinking_content = ""
        self.is_streaming = False
        self.is_thinking = False
        self.response_phase = ResponsePhase.IDLE
        self.active_tools.clear()
