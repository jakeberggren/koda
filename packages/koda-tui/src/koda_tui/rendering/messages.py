"""Messages: chat messages as prompt_toolkit fragments, laid out at a width."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import FormattedText
from rich.padding import Padding

from koda_tui.appearance import Spacing, Tokens, compose
from koda_tui.appearance.rich import render
from koda_tui.rendering.markdown import Markdown
from koda_tui.rendering.tools import render_tool_call
from koda_tui.state import MessageRole

if TYPE_CHECKING:
    from koda_tui.state import Message

USER_PADDING = (Spacing.GAP, 0, Spacing.GAP, Spacing.EDGE)  # Top, right, bottom, left.
THINKING_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)
GAP = "\n" * (Spacing.GAP + 1)  # Ends a line, then leaves blank rows.


def render_message(message: Message, width: int) -> FormattedText:
    """A message by its role: the user's on a raised block, the assistant's after its
    thinking, a tool's as its call and result."""
    match message.role:
        case MessageRole.USER:
            block = Padding(Markdown(message.content), USER_PADDING, style=Tokens.Surface.RAISED)
            return render(block, width)
        case MessageRole.ASSISTANT:
            return _assistant(message, width)
        case MessageRole.TOOL if message.tool_call:
            call = render_tool_call(
                message.tool_call,
                running=message.tool_running,
                error=message.tool_error,
                display=_display(message),
                content=message.tool_result_content,
            )
            return render(call, width)
        case MessageRole.TOOL:
            return FormattedText([])


def render_streaming(content: str, width: int) -> FormattedText:
    """A reply still streaming."""
    return render(Markdown(content), width)


def render_thinking(content: str, width: int) -> FormattedText:
    """Thinking, muted, whether streaming or kept with its reply."""
    return render(Markdown(content, style=THINKING_STYLE), width)


def _assistant(message: Message, width: int) -> FormattedText:
    parts: list[FormattedText] = []
    if message.thinking_content:
        parts.append(render_thinking(message.thinking_content, width))
    if message.content:
        parts.append(render_streaming(message.content, width))
    fragments = FormattedText()
    for index, part in enumerate(parts):
        if index:
            fragments.append(("", GAP))
        fragments.extend(part)
    return fragments


def _display(message: Message) -> str | None:
    """The result to show: the tool's own, or its error message if it failed without one."""
    if not message.tool_result_display and message.tool_error and message.tool_error_message:
        return message.tool_error_message
    return message.tool_result_display
