"""Scroll primitive: blocks of text fitted to the width, in a viewport that follows the end."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import UIContent, UIControl, Window
from prompt_toolkit.layout.margins import ConditionalMargin, Margin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from koda_tui.appearance import Spacing, Tokens
from koda_tui.ui.fragments import fit

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from prompt_toolkit.filters import FilterOrBool
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout import WindowRenderInfo

    type Blocks = Callable[[int], Sequence[StyleAndTextTuples]]

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
    """The blocks from ``blocks(width)``, ``gap`` blank rows apart, scrolled by ``state``.

    Each block is fitted to the width like a wrapping Text: split at newlines, and
    lines too wide wrapped by word. A block is fitted again only when it is a new
    object or the width changes, so return the same object for a block that hasn't
    changed. A scrollbar shows while the lines overflow, if ``scrollbar`` allows.
    """

    def __init__(
        self,
        state: ScrollState,
        blocks: Blocks,
        *,
        gap: int = 0,
        scrollbar: FilterOrBool = True,
    ) -> None:
        self._window = Window(
            ScrollControl(state, blocks, gap=gap),
            right_margins=[ConditionalMargin(ScrollbarMargin(state), filter=scrollbar)],
        )

    def __pt_container__(self) -> Window:
        return self._window


class ScrollControl(UIControl):
    """Draws the visible lines and scrolls on the mouse wheel."""

    def __init__(self, state: ScrollState, blocks: Blocks, *, gap: int) -> None:
        self._state = state
        self._blocks = blocks
        self._gap = gap
        self._width = 0
        self._fitted: dict[int, tuple[StyleAndTextTuples, list[StyleAndTextTuples]]] = {}

    def lines(self, width: int) -> list[StyleAndTextTuples]:
        """Every block's lines at ``width``, with the gaps between them."""
        if width != self._width:
            self._fitted.clear()
            self._width = width
        blocks = self._blocks(width)
        for stale in self._fitted.keys() - {id(block) for block in blocks}:
            del self._fitted[stale]

        lines: list[StyleAndTextTuples] = []
        for index, block in enumerate(blocks):
            if index:
                lines.extend([] for _ in range(self._gap))
            lines.extend(self._fit(block, width))
        return lines

    def _fit(self, block: StyleAndTextTuples, width: int) -> list[StyleAndTextTuples]:
        cached = self._fitted.get(id(block))
        if cached is not None and cached[0] is block:
            return cached[1]
        lines = fit(block, width)
        self._fitted[id(block)] = (block, lines)
        return lines

    @override
    def create_content(self, width: int, height: int) -> UIContent:
        lines = self.lines(width)
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
