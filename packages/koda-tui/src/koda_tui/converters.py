from __future__ import annotations

from typing import TYPE_CHECKING

from koda.messages import AssistantMessage, Message, SystemMessage, ToolMessage, UserMessage
from koda_tui.state import Message as TUIMessage
from koda_tui.state import MessageRole

if TYPE_CHECKING:
    from collections.abc import Sequence


def convert_messages(messages: Sequence[Message]) -> list[TUIMessage]:  # noqa: C901 - allow for now
    """Convert koda core messages to TUI messages.

    Walks the message list in order, properly linking tool results
    back to their corresponding tool calls via call_id.
    """
    result: list[TUIMessage] = []
    tool_msg_by_call_id: dict[str, TUIMessage] = {}

    for msg in messages:
        if isinstance(msg, SystemMessage):
            continue

        if isinstance(msg, UserMessage):
            result.append(TUIMessage(role=MessageRole.USER, content=msg.content))

        elif isinstance(msg, AssistantMessage):
            if msg.content:
                result.append(TUIMessage(role=MessageRole.ASSISTANT, content=msg.content))
            for tc in msg.tool_calls:
                tui_msg = TUIMessage(
                    role=MessageRole.TOOL,
                    content=f"Tool: {tc.tool_name}",
                    tool_call=tc,
                    tool_running=False,
                )
                result.append(tui_msg)
                tool_msg_by_call_id[tc.call_id] = tui_msg

        elif isinstance(msg, ToolMessage):
            existing = tool_msg_by_call_id.get(msg.tool_result.call_id)
            if existing is not None:
                existing.tool_result_display = msg.tool_result.output.display
                existing.tool_error = msg.tool_result.output.is_error
                existing.tool_error_message = msg.tool_result.output.error_message
            else:
                result.append(
                    TUIMessage(
                        role=MessageRole.TOOL,
                        content=f"Tool: {msg.tool_name}",
                        tool_error=msg.tool_result.output.is_error,
                        tool_result_display=msg.tool_result.output.display,
                        tool_error_message=msg.tool_result.output.error_message,
                    )
                )

    return result
