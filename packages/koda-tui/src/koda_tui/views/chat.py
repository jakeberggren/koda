"""Chat: the conversation, rendered and scrolled."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.layout import HSplit, VSplit, Window
from prompt_toolkit.utils import get_cwidth

from koda_tui.appearance import Spacing
from koda_tui.rendering import render_message
from koda_tui.ui.primitives import Scroll, ScrollState, Spacer

if TYPE_CHECKING:
    from prompt_toolkit.filters import FilterOrBool
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.state import AppState, Message


class Chat:
    """The messages, following the end; the reply being streamed is the last one.

    Rendered lines are cached per message until the width changes. Messages never
    change; a message with news, like a tool's result, is a new message.
    """

    def __init__(self, state: AppState, *, scrollbar: FilterOrBool = True) -> None:
        self._state = state
        self._width = 0
        self._cache: dict[int, tuple[Message, list[StyleAndTextTuples]]] = {}
        self._container = HSplit(
            [
                Spacer(),
                VSplit(
                    [
                        Window(width=Spacing.EDGE),
                        Scroll(
                            ScrollState(),
                            self._lines,
                            scrollbar=scrollbar,
                        ),
                    ],
                ),
            ],
        )

    def __pt_container__(self) -> HSplit:
        return self._container

    def clear_caches(self) -> None:
        """Render every message again on the next frame."""
        self._cache.clear()

    def _lines(self, width: int) -> list[StyleAndTextTuples]:
        if width != self._width:
            self.clear_caches()
            self._width = width
        self._drop_stale()

        lines: list[StyleAndTextTuples] = []
        for message in self._state.messages:
            lines.extend(self._message_lines(message, width))
            lines.append([])  # A blank line between messages.

        return lines or [[]]

    def _message_lines(self, message: Message, width: int) -> list[StyleAndTextTuples]:
        cached = self._cache.get(id(message))
        if cached is not None and cached[0] is message:
            return cached[1]
        lines = _fit(render_message(message, width), width)
        self._cache[id(message)] = (message, lines)
        return lines

    def _drop_stale(self) -> None:
        """Forget messages that are no longer in the conversation."""
        current = {id(message) for message in self._state.messages}
        for stale in self._cache.keys() - current:
            del self._cache[stale]


def _fit(fragments: StyleAndTextTuples, width: int) -> list[StyleAndTextTuples]:
    """Split ``fragments`` into lines at newlines, wrapping any line wider than ``width``.

    Rich already wraps to ``width``, but it measures some emoji (skin tones, ZWJ
    sequences, flags) narrower than prompt_toolkit draws them.
    """
    lines = [wrapped for line in split_lines(fragments) for wrapped in _wrap(line, width)]
    if len(lines) > 1 and not lines[-1]:
        lines.pop()  # The text ended with a newline.
    return lines


def _wrap(line: StyleAndTextTuples, width: int) -> list[StyleAndTextTuples]:
    """``line`` broken into lines at most ``width`` wide, by character."""
    lines: list[StyleAndTextTuples] = [[]]
    used = 0
    for style, text, *_ in line:
        for char in text:
            char_width = get_cwidth(char)
            if used + char_width > width and lines[-1]:
                lines.append([])
                used = 0
            lines[-1].append((style, char))
            used += char_width
    return lines
