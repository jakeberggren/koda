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
        control = RowsControl(lines, on_scroll)
        self._window = Window(
            control,
            height=height,
            dont_extend_height=True,
            get_vertical_scroll=control.vertical_scroll,
        )

    def __pt_container__(self) -> Window:
        return self._window


class RowsControl(UIControl):
    """Hands the window every line, with the cursor on the selected one, so the window
    scrolls as little as it takes to show it."""

    def __init__(self, lines: Callable[[], Lines], on_scroll: Callable[[int], None] | None) -> None:
        self._lines = lines
        self._on_scroll = on_scroll
        self._shown = Lines([])  # As last drawn.
        self._height = 0  # As last drawn.

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
        shown = self._shown = self._lines()
        self._height = height
        lines = shown.lines

        def get_line(i: int) -> StyleAndTextTuples:
            return lines[i] if 0 <= i < len(lines) else []

        selected = 0 if shown.selected is None else shown.selected
        return UIContent(
            get_line=get_line,
            line_count=len(lines),
            cursor_position=Point(x=0, y=selected),
        )

    def vertical_scroll(self, window: Window) -> int:
        """Where the window scrolls from: where it is, or up at the anchor when the
        anchor and the selected line fit together."""
        selected, anchor = self._shown.selected, self._shown.anchor
        start = window.vertical_scroll
        fits = selected is not None and anchor is not None and selected - anchor < self._height
        return anchor if fits and anchor < start else start

    @override
    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        if self._on_scroll is None:
            return
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._on_scroll(-1)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._on_scroll(1)
