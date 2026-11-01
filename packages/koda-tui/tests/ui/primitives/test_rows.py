"""Tests for the Rows primitive: which lines show, and where the cursor is."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import Window, to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

from koda_tui.ui.primitives import Lines, Rows

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples

HEIGHT = 3


class _Shown:
    """Rows over ten lines, "0" to "9", with the selection and anchor set by the test."""

    def __init__(self, *, on_scroll: Callable[[int], None] | None = None) -> None:
        self.selected: int | None = 0
        self.anchor: int | None = None
        self.window = cast("Window", to_container(Rows(self._lines, on_scroll=on_scroll)))

    def _lines(self) -> Lines:
        lines: list[StyleAndTextTuples] = [[("", str(index))] for index in range(10)]
        return Lines(lines, selected=self.selected, anchor=self.anchor)

    def draw(self) -> tuple[list[str], Point]:
        """The rows the window shows, and the cursor among them."""
        screen = Screen()
        self.window.write_to_screen(
            screen,
            MouseHandlers(),
            WritePosition(xpos=0, ypos=0, width=10, height=HEIGHT),
            parent_style="",
            erase_bg=False,
            z_index=None,
        )
        rows = [
            "".join(screen.data_buffer[y][x].char for x in range(10)).rstrip()
            for y in range(HEIGHT)
        ]
        info = self.window.render_info
        assert info is not None
        return rows, info.cursor_position

    def select(self, selected: int | None, anchor: int | None = None) -> tuple[list[str], Point]:
        self.selected, self.anchor = selected, anchor
        return self.draw()


def test_shows_the_first_lines_with_the_cursor_on_the_selected_one() -> None:
    assert _Shown().select(1) == (["0", "1", "2"], Point(x=0, y=1))


def test_scrolls_down_just_enough_to_show_the_selected_line() -> None:
    assert _Shown().select(5) == (["3", "4", "5"], Point(x=0, y=2))


def test_scrolls_up_just_enough_to_show_the_selected_line() -> None:
    shown = _Shown()
    shown.select(9)
    assert shown.select(5) == (["5", "6", "7"], Point(x=0, y=0))


def test_stays_put_while_the_selected_line_is_in_view() -> None:
    shown = _Shown()
    shown.select(5)
    assert shown.select(4) == (["3", "4", "5"], Point(x=0, y=1))


def test_shows_the_anchor_too_when_both_fit() -> None:
    shown = _Shown()
    shown.select(9)
    assert shown.select(6, anchor=4) == (["4", "5", "6"], Point(x=0, y=2))


def test_leaves_out_the_anchor_when_both_do_not_fit() -> None:
    shown = _Shown()
    shown.select(9)
    assert shown.select(6, anchor=3) == (["6", "7", "8"], Point(x=0, y=0))


def test_without_a_selection_shows_the_first_lines() -> None:
    shown = _Shown()
    shown.select(9)
    assert shown.select(None) == (["0", "1", "2"], Point(x=0, y=0))


def test_prefers_as_many_rows_as_lines() -> None:
    assert _Shown().window.content.preferred_height(10, 99, False, None) == 10  # noqa: FBT003


def test_the_mouse_wheel_asks_to_move_the_selection() -> None:
    moves: list[int] = []
    shown = _Shown(on_scroll=moves.append)
    for kind in (MouseEventType.SCROLL_DOWN, MouseEventType.SCROLL_UP):
        event = MouseEvent(Point(x=0, y=0), kind, MouseButton.NONE, frozenset())
        shown.window.content.mouse_handler(event)
    assert moves == [1, -1]
