"""Scroll primitive: a viewport over lines that follows the end as lines are added."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import UIContent, UIControl, Window
from prompt_toolkit.layout.margins import ConditionalMargin, Margin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from koda_tui.appearance import Spacing, Tokens

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.filters import FilterOrBool
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout import WindowRenderInfo

    type Lines = Callable[[int], list[StyleAndTextTuples]]

THUMB = "█"
THUMB_STYLE = Tokens.Text.DEFAULT
TRACK_STYLE = Tokens.Surface.RAISED


class ScrollState:
    """Where a scrolled view is: its first visible line, out of ``total``, ``height`` rows high.

    The view follows the end until scrolled up, and again once scrolled back down.
    """

    def __init__(self) -> None:
        self.offset = 0
        self.total = 0
        self.height = 0
        self._following = True
        self._pending = 0  # Scrolled since the last frame, applied on the next one.

    @property
    def overflowing(self) -> bool:
        """Whether there are more lines than rows."""
        return self.total > self.height

    def scroll(self, delta: int) -> None:
        """Scroll by ``delta`` lines on the next frame: negative is up."""
        self._pending += delta

    def update(self, total: int, height: int) -> None:
        """Fit the view to ``total`` lines in ``height`` rows, then apply any scrolling."""
        self.total, self.height = total, height
        end = max(0, total - height)
        self.offset = end if self._following else min(self.offset, end)
        self.offset = max(0, min(self.offset + self._pending, end))
        self._pending = 0
        self._following = self.offset >= end


class Scroll:
    """The lines from ``lines(width)``, one row each, scrolled by ``state``.

    Lines wider than the view are clipped, so ``lines`` should fit them to ``width``.
    A scrollbar shows while the lines overflow, if ``scrollbar`` allows.
    """

    def __init__(self, state: ScrollState, lines: Lines, *, scrollbar: FilterOrBool = True) -> None:
        self._window = Window(
            ScrollControl(state, lines),
            right_margins=[ConditionalMargin(ScrollbarMargin(state), filter=scrollbar)],
        )

    def __pt_container__(self) -> Window:
        return self._window


class ScrollControl(UIControl):
    """Draws the visible lines and scrolls on the mouse wheel."""

    def __init__(self, state: ScrollState, lines: Lines) -> None:
        self._state = state
        self._lines = lines

    @override
    def create_content(self, width: int, height: int) -> UIContent:
        lines = self._lines(width)
        state = self._state
        state.update(len(lines), height)

        def get_line(i: int) -> StyleAndTextTuples:
            index = state.offset + i
            return lines[index] if index < len(lines) else []

        # The cursor sits on the last visible line, so the window never scrolls by itself.
        cursor = max(0, min(height, len(lines) - state.offset) - 1)
        return UIContent(
            get_line=get_line,
            line_count=min(height, max(len(lines), 1)),
            cursor_position=Point(x=0, y=cursor),
        )

    @override
    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._state.scroll(-1)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._state.scroll(1)


class ScrollbarMargin(Margin):
    """A thumb on a track, after a gap, while the lines overflow."""

    def __init__(self, state: ScrollState) -> None:
        self._state = state

    @override
    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:
        return Spacing.GAP + len(THUMB) if self._state.overflowing else 0

    @override
    def create_margin(
        self,
        window_render_info: WindowRenderInfo,
        width: int,
        height: int,
    ) -> StyleAndTextTuples:
        state = self._state
        if not state.overflowing or height == 0:
            return []
        size = max(1, height * state.height // state.total)
        end = state.total - state.height
        start = (height - size) * state.offset // end
        gap = " " * Spacing.GAP
        rows: StyleAndTextTuples = []
        for row in range(height):
            thumb = start <= row < start + size
            rows.append(("", gap))
            rows.append((THUMB_STYLE, THUMB) if thumb else (TRACK_STYLE, " "))
            rows.append(("", "\n"))
        return rows
