"""Messages: chat messages as prompt_toolkit fragments, laid out at a width."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import FormattedText
from rich.padding import Padding

from koda_tui.appearance import Spacing, Tokens, compose
from koda_tui.appearance.rich import render
from koda_tui.rendering.markdown import Markdown
from koda_tui.rendering.tools import render_tool_call
from koda_tui.state import AssistantMessage, ErrorMessage, ToolMessage, UserMessage

if TYPE_CHECKING:
    from koda_tui.state import Message

USER_PADDING = (Spacing.GAP, 0, Spacing.GAP, Spacing.EDGE)  # Top, right, bottom, left.
THINKING_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)
GAP = "\n" * (Spacing.GAP + 1)  # Ends a line, then leaves blank rows.
ERROR_FALLBACK = "Complete the required setup and try again."


def render_message(message: Message, width: int) -> FormattedText:
    """The user's message on a raised block, a reply after its thinking, a tool as its
    call and result, and an error as its summary in bold above its detail."""
    match message:
        case UserMessage():
            block = Padding(Markdown(message.text), USER_PADDING, style=Tokens.Surface.RAISED)
            return render(block, width)
        case AssistantMessage():
            return _assistant(message, width)
        case ToolMessage():
            return render(render_tool_call(message.call, message.result), width)
        case ErrorMessage():
            detail = message.detail or ERROR_FALLBACK
            return render(Markdown(f"**{message.summary}**\n\n{detail}"), width)


def _reply(content: str, width: int) -> FormattedText:
    return render(Markdown(content), width)


def _thinking(content: str, width: int) -> FormattedText:
    """Thinking, muted."""
    return render(Markdown(content, style=THINKING_STYLE), width)


def _assistant(message: AssistantMessage, width: int) -> FormattedText:
    parts: list[FormattedText] = []
    if message.thinking:
        parts.append(_thinking(message.thinking, width))
    if message.text:
        parts.append(_reply(message.text, width))
    fragments = FormattedText()
    for index, part in enumerate(parts):
        if index:
            fragments.append(("", GAP))
        fragments.extend(part)
    return fragments
