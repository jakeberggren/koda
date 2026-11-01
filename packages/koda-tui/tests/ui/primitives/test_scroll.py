"""Tests for Scroll: fitting blocks to the width, and the state that follows the end."""

from typing import cast

from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout import Window, to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition

from koda_tui.ui.primitives import Scroll, ScrollState
from koda_tui.ui.primitives.scroll import ScrollControl


def _control(blocks: list[StyleAndTextTuples], gap: int = 0) -> ScrollControl:
    return ScrollControl(ScrollState(), lambda _width: blocks, gap=gap)


def _text(lines: list[StyleAndTextTuples]) -> list[str]:
    return ["".join(text for _, text, *_ in line) for line in lines]


def test_blocks_are_fitted_and_kept_gap_rows_apart() -> None:
    control = _control([[("", "one two three")], [("", "four")]], gap=1)
    assert _text(control.lines(8)) == ["one two", "three", "", "four"]


def test_a_block_is_fitted_again_only_when_it_changes_or_the_width_does() -> None:
    block: StyleAndTextTuples = [("", "one two")]
    control = _control([block])
    first = control.lines(10)[0]
    assert control.lines(10)[0] is first
    assert control.lines(9)[0] is not first


def test_follows_the_end_as_lines_are_added() -> None:
    state = ScrollState()
    state.update(total=30, height=10)
    assert state.offset == 20
    state.update(total=35, height=10)
    assert state.offset == 25


def test_scrolling_up_stops_following() -> None:
    state = ScrollState()
    state.update(total=30, height=10)
    state.scroll(-5)
    state.update(total=30, height=10)
    assert state.offset == 15
    state.update(total=40, height=10)
    assert state.offset == 15


def test_scrolling_back_to_the_end_follows_again() -> None:
    state = ScrollState()
    state.update(total=30, height=10)
    state.scroll(-5)
    state.update(total=30, height=10)
    state.scroll(5)
    state.update(total=30, height=10)
    state.update(total=40, height=10)
    assert state.offset == 30


def test_scrolling_stays_within_the_lines() -> None:
    state = ScrollState()
    state.update(total=30, height=10)
    state.scroll(-100)
    state.update(total=30, height=10)
    assert state.offset == 0
    state.scroll(100)
    state.update(total=30, height=10)
    assert state.offset == 20


def test_overflowing_only_with_more_lines_than_rows() -> None:
    state = ScrollState()
    state.update(total=10, height=10)
    assert not state.overflowing()
    assert state.offset == 0
    state.update(total=11, height=10)
    assert state.overflowing()


def _drawn(
    state: ScrollState,
    count: int,
    height: int = 3,
    *,
    scrollbar: bool = False,
) -> list[str]:
    """The rows a Scroll over ``count`` one-line blocks shows, ``height`` rows high."""
    blocks: list[StyleAndTextTuples] = [[("", str(index))] for index in range(count)]
    scroll = Scroll(state, lambda _width: blocks, scrollbar=scrollbar)
    window = cast("Window", to_container(scroll))
    screen = Screen()
    window.write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(xpos=0, ypos=0, width=10, height=height),
        parent_style="",
        erase_bg=False,
        z_index=None,
    )
    return [
        "".join(screen.data_buffer[y][x].char for x in range(10)).rstrip() for y in range(height)
    ]


def test_the_window_shows_the_end_while_following() -> None:
    assert _drawn(ScrollState(), 10) == ["7", "8", "9"]


def test_the_window_shows_where_the_state_is_scrolled_to() -> None:
    state = ScrollState()
    _drawn(state, 10)
    state.scroll(-4)
    assert _drawn(state, 10) == ["3", "4", "5"]


def test_the_window_shows_short_content_from_the_top() -> None:
    assert _drawn(ScrollState(), 2) == ["0", "1", ""]


def _thumb(rows: list[str]) -> list[bool]:
    return [row.endswith("█") for row in rows]


def test_the_scrollbar_thumb_shows_where_the_window_is() -> None:
    state = ScrollState()
    _drawn(state, 12, height=4, scrollbar=True)  # The first frame finds out it overflows.
    assert _thumb(_drawn(state, 12, height=4, scrollbar=True)) == [False, False, False, True]
    state.scroll(-8)
    assert _thumb(_drawn(state, 12, height=4, scrollbar=True)) == [True, False, False, False]


def test_no_scrollbar_while_everything_fits() -> None:
    assert _drawn(ScrollState(), 3, height=4, scrollbar=True) == ["0", "1", "2", ""]
