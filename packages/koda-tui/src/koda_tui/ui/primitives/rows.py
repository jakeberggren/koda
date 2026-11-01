"""Rows primitive: lines with one selected, scrolled to keep it in view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import UIContent, UIControl, Window
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable
    from prompt_toolkit.layout.dimension import AnyDimension


@dataclass(frozen=True, slots=True)
class Lines:
    """What Rows shows: its lines, the one selected, and a line to keep in view with
    it, such as the header of the selected line's group."""

    lines: Sequence[StyleAndTextTuples]
    selected: int | None = None
    anchor: int | None = None


class Rows:
    """The lines from ``lines()``, read on every render, scrolled as little as it takes to
    keep the selected line in view, and its anchor too when both fit.

    The mouse wheel calls ``on_scroll`` with -1 (up) or 1 (down), for whoever owns the
    selection to move it.
    """

    def __init__(
        self,
        lines: Callable[[], Lines],
        *,
        on_scroll: Callable[[int], None] | None = None,
        height: AnyDimension = None,
    ) -> None:
        self._window = Window(RowsControl(lines, on_scroll), height=height, dont_extend_height=True)

    def __pt_container__(self) -> Window:
        return self._window


class RowsControl(UIControl):
    """Draws the visible lines, with the cursor on the selected one."""

    def __init__(self, lines: Callable[[], Lines], on_scroll: Callable[[int], None] | None) -> None:
        self._lines = lines
        self._on_scroll = on_scroll
        self._offset = 0  # The first line shown.

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int:
        return len(self._lines().lines)

    @override
    def create_content(self, width: int, height: int) -> UIContent:
        shown = self._lines()
        height = max(1, height)
        self._offset = _scrolled(self._offset, shown, height)
        visible = shown.lines[self._offset : self._offset + height]
        cursor = 0
        if shown.selected is not None:
            cursor = max(0, min(height - 1, shown.selected - self._offset))

        def get_line(i: int) -> StyleAndTextTuples:
            return visible[i] if 0 <= i < len(visible) else []

        return UIContent(
            get_line=get_line,
            line_count=len(visible),
            cursor_position=Point(x=0, y=cursor),
        )

    @override
    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        if self._on_scroll is None:
            return
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._on_scroll(-1)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._on_scroll(1)


def _scrolled(offset: int, shown: Lines, height: int) -> int:
    """The first line to show, ``height`` rows high: ``offset`` moved as little as it
    takes to show the selected line, then up to the anchor if both fit."""
    selected, anchor = shown.selected, shown.anchor
    if selected is None:
        return 0
    if selected < offset:
        offset = selected
    elif selected >= offset + height:
        offset = selected - height + 1
    if anchor is not None and anchor < offset and selected - anchor < height:
        offset = anchor
    return max(0, min(offset, len(shown.lines) - height))
