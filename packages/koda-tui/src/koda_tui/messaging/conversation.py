"""Conversation: the chat messages in AppState, built live from agent events or from history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda import messages as core
from koda.agent import (
    AgentEvent,
    AgentResponseCompleted,
    AgentTextDelta,
    AgentThinkingDelta,
    AgentToolCallRequested,
    AgentToolCompleted,
    AgentToolResultReady,
    AgentToolStarted,
)
from koda.sessions import sum_usage
from koda.tools import ToolOutput
from koda_tui.state import AssistantMessage, ToolMessage, Usage, UserMessage

if TYPE_CHECKING:
    from collections.abc import Sequence

    from koda.messages import TokenUsage
    from koda.sessions import Session
    from koda.tools import ToolCall
    from koda_tui.state import AppState, ErrorMessage, Message


class Conversation:
    """Keeps ``state``'s messages: the exchanges so far, and the response in flight.

    A response runs from ``start`` to ``end``, with each agent event applied between.
    The reply being streamed is the last message, replaced as each chunk arrives.
    ``load`` replaces everything with a saved session's history.
    """

    def __init__(self, state: AppState) -> None:
        self._state = state

    def start(self, user_message: str) -> None:
        """Start a response to ``user_message``."""
        self._state.messages.append(UserMessage(user_message))
        self._state.responding = True

    def end(self, error: ErrorMessage | None = None) -> None:
        """End the response, with ``error`` after it if it failed, stopping any tools
        still running."""
        self._drop_blank_reply()
        messages = self._state.messages
        if error:
            messages.append(error)
        response = self._state.response()
        for index, message in enumerate(response, len(messages) - len(response)):
            if isinstance(message, ToolMessage) and message.result is None:
                messages[index] = ToolMessage(message.call, ToolOutput())
        self._state.responding = False

    def load(self, session: Session) -> None:
        """Show ``session``: its history as messages, and its token usage."""
        self._state.messages = _from_history(session.messages)
        self._state.responding = False
        latest, total = session.usage, session.total_usage
        self._state.usage = Usage(latest, total) if latest and total else None

    def clear(self) -> None:
        """Forget the messages, any response in flight, and the token usage."""
        self._state.messages = []
        self._state.responding = False
        self._state.usage = None

    def apply(self, event: AgentEvent) -> None:  # noqa: C901 - one case per kind of event
        """Apply one event of the response in flight; other events change nothing."""
        match event:
            case AgentTextDelta():
                self._stream(text=event.text)
            case AgentThinkingDelta():
                self._stream(thinking=event.text)
            case AgentResponseCompleted():
                self._add_usage(event.message.usage)
            case AgentToolCallRequested() | AgentToolStarted():
                self._start_tool(event.call)
            case AgentToolResultReady() | AgentToolCompleted():
                self._complete_tool(event.result.call_id, event.result.output)

    def _add_usage(self, latest: TokenUsage | None) -> None:
        """Count a response's usage; responses that report none leave it as it was."""
        if latest is None:
            return
        previous = self._state.usage.total if self._state.usage else None
        self._state.usage = Usage(latest, sum_usage(previous, latest) or latest)

    def _stream(self, *, text: str = "", thinking: str = "") -> None:
        """Add a chunk to the reply being streamed, starting one if the last message isn't."""
        messages = self._state.messages
        last = messages[-1] if messages else None
        if isinstance(last, AssistantMessage):
            messages[-1] = AssistantMessage(last.text + text, last.thinking + thinking)
        else:
            messages.append(AssistantMessage(text, thinking))

    def _drop_blank_reply(self) -> None:
        """Drop the reply being streamed if it is only whitespace."""
        messages = self._state.messages
        last = messages[-1] if messages else None
        if isinstance(last, AssistantMessage) and not (last.text + last.thinking).strip():
            messages.pop()

    def _start_tool(self, call: ToolCall) -> None:
        self._drop_blank_reply()
        if self._running(call.call_id) is None:
            self._state.messages.append(ToolMessage(call))

    def _complete_tool(self, call_id: str, output: ToolOutput) -> None:
        if running := self._running(call_id):
            index, message = running
            self._state.messages[index] = ToolMessage(message.call, output)

    def _running(self, call_id: str) -> tuple[int, ToolMessage] | None:
        """The running call ``call_id`` and where it is in the messages, if it is running."""
        response = self._state.response()
        start = len(self._state.messages) - len(response)
        for index, message in enumerate(response, start):
            match message:
                case ToolMessage(result=None) if message.call.call_id == call_id:
                    return index, message
        return None


def _from_history(history: Sequence[core.Message]) -> list[Message]:  # noqa: C901 - one case per kind of message
    """Messages for a saved history, each tool call with its result. A call without a
    result shows as done; a result with no call to show it under is left out."""
    messages: list[Message] = []
    tools: dict[str, tuple[int, ToolCall]] = {}  # By call id: where its message is, and the call.
    for item in history:
        match item:
            case core.UserMessage():
                messages.append(UserMessage(item.content))
            case core.AssistantMessage():
                if reply := _assistant_message(item.content, item.thinking_content):
                    messages.append(reply)
                for call in item.tool_calls:
                    tools[call.call_id] = (len(messages), call)
                    messages.append(ToolMessage(call, ToolOutput()))
            case core.ToolMessage() if item.tool_result.call_id in tools:
                index, call = tools[item.tool_result.call_id]
                messages[index] = ToolMessage(call, item.tool_result.output)
    return messages


def _assistant_message(text: str, thinking: str) -> AssistantMessage | None:
    """A reply with its thinking, or None if both are blank."""
    if not text.strip() and not thinking.strip():
        return None
    return AssistantMessage(text, thinking)
