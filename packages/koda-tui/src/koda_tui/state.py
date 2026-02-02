from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

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
    tool_running: bool = False
    tool_error: bool = False
    tool_result_display: str | None = None


@dataclass
class AppState:
    """Shared application state as single source of truth for the UI."""

    messages: list[Message] = field(default_factory=list)
    cwd: Path = field(default_factory=lambda: Path.cwd())
    current_streaming_content: str = ""
    is_streaming: bool = False
    active_tools: dict[str, ToolCall] = field(default_factory=dict)
    model_name: str = ""
    provider_name: str = ""
    show_scrollbar: bool = True
    exit_requested: bool = False
    palette_open: bool = False

    def append_delta(self, text: str) -> None:
        """Append text to current streaming message."""
        self.current_streaming_content += text

    def complete_tool_message(
        self,
        call_id: str,
        display: str | None = None,
        *,
        is_error: bool | None = None,
    ) -> None:
        """Mark the running tool message as complete."""
        for message in reversed(self.messages):
            if (
                message.role == MessageRole.TOOL
                and message.tool_call
                and message.tool_call.call_id == call_id
            ):
                message.tool_running = False
                if is_error is not None:
                    message.tool_error = is_error
                if display is not None:
                    message.tool_result_display = display
                break

    def reset_exit_request(self) -> None:
        """Reset the exit request flag."""
        self.exit_requested = False

    def request_exit(self) -> bool:
        """Request application exit. Returns True if should exit immediately."""
        if self.exit_requested:
            return True
        self.exit_requested = True
        return False

    def begin_response(self, user_message: str) -> None:
        """Atomically begin a new response cycle."""
        self.reset_exit_request()
        self.messages.append(Message(role=MessageRole.USER, content=user_message))
        self.is_streaming = True
        self.current_streaming_content = ""

    def transition_to_tool(self, tool_call: ToolCall) -> None:
        """Atomically transition from streaming content to tool execution."""
        # Finalize any pending content
        if self.current_streaming_content:
            self.messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=self.current_streaming_content,
                )
            )
            self.current_streaming_content = ""

        self.active_tools[tool_call.call_id] = tool_call
        self.messages.append(
            Message(
                role=MessageRole.TOOL,
                content=f"Tool: {tool_call.tool_name}",
                tool_call=tool_call,
                tool_running=True,
            )
        )

    def end_response(self) -> None:
        """Atomically end the response cycle."""
        # Finalize any pending content
        if self.current_streaming_content:
            self.messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=self.current_streaming_content,
                )
            )

        # Complete any remaining active tools
        for call_id in list(self.active_tools):
            self.complete_tool_message(call_id)
        self.active_tools.clear()

        # Reset state
        self.is_streaming = False
        self.current_streaming_content = ""
