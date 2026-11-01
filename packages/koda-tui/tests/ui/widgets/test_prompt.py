"""Tests for the Prompt widget beside content taller than one row."""

from __future__ import annotations

from prompt_toolkit.layout import FormattedTextControl, VSplit, Window, to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition

from koda_tui.appearance import Icons, Tokens
from koda_tui.ui.widgets import Prompt


def _screen(row: VSplit, width: int, height: int) -> Screen:
    screen = Screen()
    to_container(row).write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(0, 0, width, height),
        "",
        erase_bg=False,
        z_index=None,
    )
    return screen


def test_prompt_column_keeps_the_surrounding_style_beside_taller_content() -> None:
    row = VSplit([Prompt(), Window(height=3)], style=Tokens.Surface.RAISED)
    screen = _screen(row, width=10, height=3)

    assert screen.data_buffer[0][0].char == Icons.PROMPT
    assert all(Tokens.Surface.RAISED in screen.data_buffer[y][0].style for y in range(3))


def test_prompt_is_as_wide_as_its_glyph() -> None:
    row = VSplit([Prompt(), Window(FormattedTextControl("hello"))])
    screen = _screen(row, width=10, height=1)

    assert "".join(screen.data_buffer[0][x].char for x in range(6)) == f"{Icons.PROMPT}hello"
