from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from koda_common.contracts import ToolCall


class MessageRole(Enum):
    """Role of a message in the chat history."""

    USER = auto()
    ASSISTANT = auto()
    TOOL = auto()


@dataclass
class Message:
    """A single message in the chat history."""

    role: MessageRole
    content: str
    tool_call: ToolCall | None = None
    tool_running: bool = False
    tool_error: bool = False
    tool_result_display: str | None = None
    tool_error_message: str | None = None


@dataclass
class AppState:
    """Shared application state as single source of truth for the UI."""

    messages: list[Message] = field(default_factory=list)
    cwd: Path = field(default_factory=Path.cwd)
    current_streaming_content: str = ""
    is_streaming: bool = False
    active_tools: dict[str, ToolCall] = field(default_factory=dict)
    pending_inputs: list[str] = field(default_factory=list)
    model_name: str = ""
    provider_name: str = ""
    show_scrollbar: bool = True
    queue_inputs: bool = True
    exit_requested: bool = False
    palette_open: bool = False

    def reset_conversation(self) -> None:
        """Clear all conversation and streaming state."""
        self.messages.clear()
        self.current_streaming_content = ""
        self.is_streaming = False
        self.active_tools.clear()
