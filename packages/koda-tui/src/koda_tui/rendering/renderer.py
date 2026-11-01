"""Renderer: what each chat message looks like, and the conversation rendered as fragments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group
from rich.padding import Padding
from rich.text import Text

from koda_tui.appearance import Spacing, Tokens, compose
from koda_tui.rendering.markdown import Markdown
from koda_tui.rendering.rich import render
from koda_tui.rendering.tools import render_tool_call
from koda_tui.state import AssistantMessage, ErrorMessage, ToolMessage, UserMessage

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from rich.console import RenderableType

    from koda_tui.state import AppState, Message

USER_PADDING = (Spacing.GAP, 0, Spacing.GAP, Spacing.EDGE)  # Top, right, bottom, left.
THINKING_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)
ERROR_FALLBACK = "Complete the required setup and try again."


class MessageRenderer:
    """Renders the state's messages to fragments, keeping each until the width
    changes or the message is gone.

    Messages never change; a message with news, like a tool's result, is a new
    message. So a message is rendered again only when it is a new object.
    """

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._width = 0
        self._rendered: dict[int, tuple[Message, StyleAndTextTuples]] = {}

    def render(self, width: int) -> list[StyleAndTextTuples]:
        """Each of the state's messages as fragments at ``width``, in order."""
        messages = self._state.messages
        if width != self._width:
            self._rendered.clear()
            self._width = width
        for stale in self._rendered.keys() - {id(message) for message in messages}:
            del self._rendered[stale]
        return [self._message(message, width) for message in messages]

    def _message(self, message: Message, width: int) -> StyleAndTextTuples:
        cached = self._rendered.get(id(message))
        if cached is not None and cached[0] is message:
            return cached[1]
        fragments = render(message_renderable(message), width)
        self._rendered[id(message)] = (message, fragments)
        return fragments


def message_renderable(message: Message) -> RenderableType:
    """The user's message on a raised block, a reply after its thinking, a tool as its
    call and result, and an error as its summary in bold above its detail."""
    match message:
        case UserMessage():
            return Padding(Markdown(message.text), USER_PADDING, style=Tokens.Surface.RAISED)
        case AssistantMessage():
            return _assistant(message)
        case ToolMessage():
            return render_tool_call(message.call, message.result)
        case ErrorMessage():
            detail = message.detail or ERROR_FALLBACK
            return Markdown(f"**{message.summary}**\n\n{detail}")


def _assistant(message: AssistantMessage) -> Group:
    """The thinking, muted, then the reply, a gap apart; either may be empty."""
    parts: list[RenderableType] = []
    if message.thinking:
        parts.append(Markdown(message.thinking, style=THINKING_STYLE))
    if message.text:
        if parts:
            parts.extend(Text() for _ in range(Spacing.GAP))
        parts.append(Markdown(message.text))
    return Group(*parts)
