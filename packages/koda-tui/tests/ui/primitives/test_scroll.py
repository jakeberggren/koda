"""Tests for Scroll: fitting blocks to the width, and the state that follows the end."""

from prompt_toolkit.formatted_text import StyleAndTextTuples

from koda_tui.ui.primitives import ScrollState
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
    assert not state.overflowing
    assert state.offset == 0
    state.update(total=11, height=10)
    assert state.overflowing
