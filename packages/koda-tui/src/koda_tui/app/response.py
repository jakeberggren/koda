from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.state import Message, MessageRole

if TYPE_CHECKING:
    from koda_service.types import ToolCall
    from koda_tui.state import AppState


class ResponseLifecycle:
    """Manages state transitions during a response cycle."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def begin(self, user_message: str) -> None:
        """Begin a new response cycle."""
        self._state.exit_requested = False
        self._state.messages.append(Message(role=MessageRole.USER, content=user_message))
        self._state.is_streaming = True
        self._state.current_streaming_content = ""
        self._state.current_thinking_content = ""

    def append_content(self, text: str) -> None:
        """Append text to current streaming content."""
        self._state.current_streaming_content += text

    def append_thinking(self, text: str) -> None:
        """Append text to current streaming thinking content."""
        self._state.current_thinking_content += text

    def transition_to_tool(self, tool_call: ToolCall) -> None:
        """Transition from streaming content to tool execution."""
        self._finalize_content()
        self._state.active_tools[tool_call.call_id] = tool_call
        self._state.messages.append(
            Message(
                role=MessageRole.TOOL,
                content=f"Tool: {tool_call.tool_name}",
                tool_call=tool_call,
                tool_running=True,
            )
        )

    def complete_tool(
        self,
        *,
        call_id: str,
        display: str | None = None,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> None:
        """Mark a running tool message as complete."""
        for message in reversed(self._state.messages):
            if (
                message.role == MessageRole.TOOL
                and message.tool_call
                and message.tool_call.call_id == call_id
                and message.tool_running
            ):
                message.tool_running = False
                message.tool_error = is_error
                message.tool_error_message = error_message
                message.tool_result_display = display or (error_message if is_error else None)
                break

    def end(self) -> None:
        """End the response cycle."""
        self._finalize_content()

        for call_id in list(self._state.active_tools):
            self.complete_tool(call_id=call_id)
        self._state.active_tools.clear()

        self._state.is_streaming = False
        self._state.current_streaming_content = ""
        self._state.current_thinking_content = ""

    def _finalize_content(self) -> None:
        """Save any pending streaming content as an assistant message."""
        if self._state.current_streaming_content or self._state.current_thinking_content:
            self._state.messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=self._state.current_streaming_content,
                    thinking_content=self._state.current_thinking_content,
                )
            )
            self._state.current_streaming_content = ""
            self._state.current_thinking_content = ""
