"""Application state management for Koda TUI."""

from dataclasses import dataclass, field
from enum import Enum, auto

from koda.tools import ToolCall


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
    is_streaming: bool = False


@dataclass
class AppState:
    """Central application state."""

    messages: list[Message] = field(default_factory=list)
    current_streaming_content: str = ""
    is_streaming: bool = False
    active_tool: ToolCall | None = None
    model_name: str = ""
    provider_name: str = ""
    error_message: str | None = None
    exit_requested: bool = False

    def start_streaming(self) -> None:
        """Begin a new assistant response."""
        self.is_streaming = True
        self.current_streaming_content = ""

    def append_delta(self, text: str) -> None:
        """Append text to current streaming message."""
        self.current_streaming_content += text

    def finish_streaming(self) -> None:
        """Finalize streaming and add to history."""
        if self.current_streaming_content:
            self.messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=self.current_streaming_content,
                )
            )
        self.is_streaming = False
        self.current_streaming_content = ""

    def set_active_tool(self, tool_call: ToolCall | None) -> None:
        """Set or clear the active tool."""
        self.active_tool = tool_call

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.messages.append(Message(role=MessageRole.USER, content=content))

    def add_tool_message(self, tool_call: ToolCall) -> None:
        """Add a tool call message to history."""
        self.messages.append(
            Message(
                role=MessageRole.TOOL,
                content=f"Tool: {tool_call.tool_name}",
                tool_call=tool_call,
            )
        )

    def request_exit(self) -> bool:
        """Request application exit. Returns True if should exit immediately."""
        if self.exit_requested:
            return True
        self.exit_requested = True
        return False

    def reset_exit_request(self) -> None:
        """Reset the exit request flag."""
        self.exit_requested = False
