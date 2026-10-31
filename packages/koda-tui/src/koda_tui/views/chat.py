"""Chat: the conversation, rendered and scrolled."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import HSplit, VSplit, Window

from koda_tui.appearance import Spacing
from koda_tui.rendering import render_message
from koda_tui.ui.primitives import Scroll, ScrollState, Spacer

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.state import AppState, Message


class Chat:
    """The messages, a blank line apart, following the end; the reply being streamed
    is the last one.

    Each message is rendered once per width. Messages never change; a message with
    news, like a tool's result, is a new message.
    """

    def __init__(self, state: AppState, *, scrollbar: FilterOrBool = True) -> None:
        self._state = state
        self._width = 0
        self._rendered: dict[int, tuple[Message, StyleAndTextTuples]] = {}
        self._container = HSplit(
            [
                Spacer(),
                VSplit(
                    [
                        Window(width=Spacing.EDGE),
                        Scroll(ScrollState(), self._blocks, gap=Spacing.GAP, scrollbar=scrollbar),
                    ],
                ),
            ],
        )

    def __pt_container__(self) -> HSplit:
        return self._container

    def _blocks(self, width: int) -> list[StyleAndTextTuples]:
        if width != self._width:
            self._rendered.clear()
            self._width = width
        messages = self._state.messages
        for stale in self._rendered.keys() - {id(message) for message in messages}:
            del self._rendered[stale]
        return [self._render(message, width) for message in messages]

    def _render(self, message: Message, width: int) -> StyleAndTextTuples:
        cached = self._rendered.get(id(message))
        if cached is not None and cached[0] is message:
            return cached[1]
        fragments = render_message(message, width)
        self._rendered[id(message)] = (message, fragments)
        return fragments
