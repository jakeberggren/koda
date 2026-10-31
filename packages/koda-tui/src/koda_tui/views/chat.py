"""Chat: the conversation, rendered and scrolled."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.layout import HSplit, VSplit, Window
from prompt_toolkit.utils import get_cwidth

from koda_tui.appearance import Spacing
from koda_tui.rendering import render_message, render_streaming, render_thinking
from koda_tui.ui.primitives import Scroll, ScrollState, Spacer

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.state import AppState, Message


class Chat:
    """The messages, then any thinking and reply still streaming, following the end.

    Rendered lines are cached per message until the message or the width changes.
    """

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._width = 0
        self._cache: dict[int, tuple[tuple, list[StyleAndTextTuples]]] = {}
        self._container = HSplit(
            [
                Spacer(),
                VSplit(
                    [
                        Window(width=Spacing.EDGE),
                        Scroll(
                            ScrollState(),
                            self._lines,
                            scrollbar=Condition(lambda: state.show_scrollbar),
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

        if self._state.is_streaming and self._state.current_thinking_content:
            thinking = render_thinking(self._state.current_thinking_content, width)
            lines.extend(_fit(thinking, width))
            lines.append([])

        if self._state.is_streaming and self._state.current_streaming_content:
            reply = render_streaming(self._state.current_streaming_content, width)
            lines.extend(_fit(reply, width))

        return lines or [[]]

    def _message_lines(self, message: Message, width: int) -> list[StyleAndTextTuples]:
        key = _cache_key(message)
        cached = self._cache.get(id(message))
        if cached is not None and cached[0] == key:
            return cached[1]
        lines = _fit(render_message(message, width), width)
        self._cache[id(message)] = (key, lines)
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


def _cache_key(message: Message) -> tuple:
    """Everything about ``message`` that changes how it renders."""
    return (
        message.role,
        message.content,
        message.thinking_content,
        message.tool_call.call_id if message.tool_call else None,
        message.tool_running,
        message.tool_error,
        message.tool_result_display,
        _freeze(message.tool_result_content),
        message.tool_error_message,
    )


def _freeze(value: Any) -> Any:
    """``value`` as something hashable and comparable, for a cache key."""
    if isinstance(value, dict):
        return tuple((k, _freeze(v)) for k, v in sorted(value.items()))
    if isinstance(value, list | tuple):
        return tuple(_freeze(v) for v in value)
    try:
        hash(value)
    except TypeError:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
