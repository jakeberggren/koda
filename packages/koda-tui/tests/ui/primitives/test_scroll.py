"""Tests for the scroll state: following the end, scrolling and clamping."""

from koda_tui.ui.primitives import ScrollState


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
