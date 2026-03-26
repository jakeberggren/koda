from __future__ import annotations

from typing import TYPE_CHECKING

from koda_service.types import (
    AssistantMessage,
    Message,
    ToolMessage,
    UserMessage,
)
from koda_tui.state import Message as TUIMessage
from koda_tui.state import MessageRole, TokenUsage, add_usage

if TYPE_CHECKING:
    from collections.abc import Sequence


def _append_user_message(result: list[TUIMessage], message: UserMessage) -> None:
    result.append(TUIMessage(role=MessageRole.USER, content=message.content))


def _append_assistant_message(
    result: list[TUIMessage],
    tool_msg_by_call_id: dict[str, TUIMessage],
    message: AssistantMessage,
) -> None:
    if message.content or message.thinking_content:
        result.append(
            TUIMessage(
                role=MessageRole.ASSISTANT,
                content=message.content,
                thinking_content=message.thinking_content,
            )
        )

    for tool_call in message.tool_calls:
        tool_message = TUIMessage(
            role=MessageRole.TOOL,
            content=f"Tool: {tool_call.tool_name}",
            tool_call=tool_call,
            tool_running=False,
        )
        result.append(tool_message)
        tool_msg_by_call_id[tool_call.call_id] = tool_message


def _apply_tool_result(
    result: list[TUIMessage],
    tool_msg_by_call_id: dict[str, TUIMessage],
    message: ToolMessage,
) -> None:
    existing = tool_msg_by_call_id.get(message.tool_result.call_id)
    if existing is not None:
        existing.tool_result_display = message.tool_result.output.display
        existing.tool_error = message.tool_result.output.is_error
        existing.tool_error_message = message.tool_result.output.error_message
        return

    result.append(
        TUIMessage(
            role=MessageRole.TOOL,
            content=f"Tool: {message.tool_name}",
            tool_error=message.tool_result.output.is_error,
            tool_result_display=message.tool_result.output.display,
            tool_error_message=message.tool_result.output.error_message,
        )
    )


def _map_usage(message: AssistantMessage) -> TokenUsage | None:
    usage = message.usage
    if usage is None:
        return None
    return TokenUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cached_tokens=usage.cached_tokens,
        total_tokens=usage.total_tokens,
    )


def convert_messages(messages: Sequence[Message]) -> tuple[list[TUIMessage], TokenUsage | None]:
    """Convert service messages to TUI messages and restore aggregated usage."""
    result: list[TUIMessage] = []
    tool_msg_by_call_id: dict[str, TUIMessage] = {}
    usage: TokenUsage | None = None

    for message in messages:
        if isinstance(message, UserMessage):
            _append_user_message(result, message)
        elif isinstance(message, AssistantMessage):
            _append_assistant_message(result, tool_msg_by_call_id, message)
            usage = add_usage(usage, _map_usage(message))
        elif isinstance(message, ToolMessage):
            _apply_tool_result(result, tool_msg_by_call_id, message)

    return result, usage
