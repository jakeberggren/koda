from __future__ import annotations

from typing import TYPE_CHECKING

from koda_service.types import (
    ProviderToolStarted,
    ResponseCompleted,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    ToolCallRequested,
)
from koda_tui.state import AppState, Message, MessageRole, ResponsePhase, TokenUsage

if TYPE_CHECKING:
    from koda_service.types import ToolCall


class ResponseLifecycle:
    """Manages state transitions during a response cycle."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def begin(self, user_message: str) -> None:
        """Begin a new response cycle."""
        self._state.exit_requested = False
        self._state.messages.append(Message(role=MessageRole.USER, content=user_message))
        self._state.is_streaming = True
        self._state.is_thinking = False
        self._state.current_streaming_content = ""
        self._state.current_thinking_content = ""
        self._state.response_phase = ResponsePhase.WORKING

    def set_usage(self, event: ResponseCompleted) -> None:
        """Persist token usage for the latest completed response."""
        if event.usage is None:
            self._state.latest_usage = None
            return
        self._state.latest_usage = TokenUsage(
            input_tokens=event.usage.input_tokens,
            output_tokens=event.usage.output_tokens,
            cached_tokens=event.usage.cached_tokens,
            total_tokens=event.usage.total_tokens,
        )

    def append_content(self, text: str) -> None:
        """Append text to current streaming content."""
        self._state.current_streaming_content += text
        self._state.is_thinking = False
        self._state.response_phase = ResponsePhase.RESPONDING

    def append_thinking(self, text: str) -> None:
        """Append text to current streaming thinking content."""
        self._state.current_thinking_content += text
        self._state.is_thinking = True
        if self._state.response_phase is not ResponsePhase.TOOLS:
            self._state.response_phase = ResponsePhase.WORKING

    def transition_to_tool(self, tool_call: ToolCall) -> None:
        """Transition from streaming content to tool execution."""
        self._finalize_content()
        self._state.is_thinking = False
        if tool_call.call_id in self._state.active_tools:
            self._state.response_phase = ResponsePhase.TOOLS
            return

        self._state.active_tools[tool_call.call_id] = tool_call
        self._state.response_phase = ResponsePhase.TOOLS
        self._state.messages.append(
            Message(
                role=MessageRole.TOOL,
                content=f"Tool: {tool_call.tool_name}",
                tool_call=tool_call,
                tool_running=True,
            )
        )

    def apply_event(self, event: StreamEvent) -> None:
        """Apply a streamed service event to the current response state."""
        if isinstance(event, TextDelta):
            self.append_content(event.text)
            return
        if isinstance(event, ThinkingDelta):
            self.append_thinking(event.text)
            return
        if isinstance(event, ResponseCompleted):
            self.set_usage(event)
            return
        if isinstance(event, ToolCallRequested | ProviderToolStarted):
            self.transition_to_tool(event.call)
            return
        self.complete_tool(
            call_id=event.result.call_id,
            display=event.result.output.display,
            is_error=event.result.output.is_error,
            error_message=event.result.output.error_message,
        )

    def _set_phase_after_tool_completion(self) -> None:
        """Update phase after a tool completes based on remaining in-flight state."""
        if self._state.active_tools:
            self._state.response_phase = ResponsePhase.TOOLS
        elif self._state.current_streaming_content:
            self._state.is_thinking = False
            self._state.response_phase = ResponsePhase.RESPONDING
        elif self._state.current_thinking_content:
            self._state.is_thinking = True
            self._state.response_phase = ResponsePhase.WORKING
        elif self._state.is_streaming:
            self._state.is_thinking = False
            self._state.response_phase = ResponsePhase.WORKING
        else:
            self._state.is_thinking = False
            self._state.response_phase = ResponsePhase.IDLE

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

        self._state.active_tools.pop(call_id, None)
        self._set_phase_after_tool_completion()

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

    def end(self) -> None:
        """End the response cycle."""
        self._finalize_content()

        for call_id in list(self._state.active_tools):
            self.complete_tool(call_id=call_id)
        self._state.active_tools.clear()

        self._state.is_streaming = False
        self._state.is_thinking = False
        self._state.current_streaming_content = ""
        self._state.current_thinking_content = ""
        self._state.response_phase = ResponsePhase.IDLE
