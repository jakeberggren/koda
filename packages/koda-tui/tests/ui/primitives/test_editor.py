from typing import cast

import pytest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.data_structures import Point
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import fragment_list_to_text
from prompt_toolkit.layout import Window, to_container
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType
from prompt_toolkit.selection import SelectionState

from koda_tui.ui.primitives import Editor
from koda_tui.ui.primitives.editor import EditorControl, _wrap_line_ranges


def _display_lines(text: str, width: int) -> list[str]:
    return [text[display_start:end] for _, end, display_start in _wrap_line_ranges(text, width)]


def test_word_after_full_width_word_does_not_render_with_leading_space() -> None:
    """A word moved after a full-width word should not render with a leading space."""
    assert _display_lines("abcde fgh", 5) == ["abcde", "fgh"]


def test_wrap_boundary_space_is_preserved_in_source_range() -> None:
    """The hidden separator should remain part of the source range for cursor mapping."""
    assert _wrap_line_ranges("abcde fgh", 5) == [(0, 5, 0), (5, 9, 6)]


def test_wrap_line_ranges_keep_trailing_space_on_non_full_line() -> None:
    """Only hide spaces that become leading indentation on continuation lines."""
    assert _display_lines("abcd ef", 5) == ["abcd ", "ef"]


# How the editor behaves as a whole: what it draws, where the cursor goes, and how
# tall it wants to be. Drawing needs a running loop, for the buffer's history.


def _editor(text: str, cursor: int | None = None) -> tuple[Window, Buffer]:
    buffer = Buffer(
        multiline=True, document=Document(text, len(text) if cursor is None else cursor)
    )
    return cast("Window", to_container(Editor(buffer))), buffer


def _draw(window: Window, width: int) -> tuple[list[str], Point]:
    """The rows drawn at ``width``, without the cursor slot that ends each, and the cursor."""
    content = window.content.create_content(width, 10)
    rows = [fragment_list_to_text(content.get_line(i)) for i in range(content.line_count)]
    assert all(row.endswith(" ") for row in rows)  # A slot for the cursor at the end.
    return [row[:-1] for row in rows], content.cursor_position


async def test_text_wraps_by_word_with_the_cursor_where_it_is() -> None:
    window, _buffer = _editor("hello world foo", cursor=6)
    assert _draw(window, 7) == (["hello ", "world ", "foo"], Point(x=0, y=1))


async def test_lines_break_at_newlines_and_wrap_within() -> None:
    window, _buffer = _editor("one\ntwo three", cursor=0)
    assert _draw(window, 6) == (["one", "two ", "three"], Point(x=0, y=0))


async def test_wide_characters_wrap_and_place_the_cursor_by_cells() -> None:
    window, _buffer = _editor("日本語 テキスト")
    assert _draw(window, 7) == (["日本語", "テキ", "スト"], Point(x=4, y=2))


async def test_empty_text_draws_one_row() -> None:
    window, _buffer = _editor("")
    assert _draw(window, 5) == ([""], Point(x=0, y=0))


@pytest.mark.parametrize(("text", "width", "rows"), [("hello world foo", 7, 3), ("", 5, 1)])
def test_preferred_height_is_the_wrapped_row_count(text: str, width: int, rows: int) -> None:
    window, _buffer = _editor(text)
    assert window.content.preferred_height(width, 99, False, None) == rows  # noqa: FBT003


async def test_cursor_moves_between_wrapped_rows_keeping_its_column() -> None:
    window, buffer = _editor("hello world foo", cursor=13)
    editor = cast("EditorControl", window.content)
    window.content.create_content(7, 10)
    positions = []
    for rows in (-1, -1, -1, 1, 1, 1):
        positions.append((editor.move_cursor_vertical(rows), buffer.cursor_position))
        window.content.create_content(7, 10)
    assert positions == [(True, 7), (True, 1), (False, 1), (True, 7), (True, 13), (False, 13)]


async def test_a_click_puts_the_cursor_under_it() -> None:
    window, buffer = _editor("hello world foo", cursor=0)
    window.content.create_content(7, 10)
    window.content.mouse_handler(
        MouseEvent(Point(x=2, y=1), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset())
    )
    assert buffer.cursor_position == 8


async def test_selected_text_is_highlighted() -> None:
    window, buffer = _editor("hello world", cursor=0)
    buffer.selection_state = SelectionState(original_cursor_position=0)
    buffer.cursor_position = 4
    line = window.content.create_content(20, 10).get_line(0)
    assert ["selected" in style for style, *_ in line][:6] == [True] * 4 + [False] * 2
