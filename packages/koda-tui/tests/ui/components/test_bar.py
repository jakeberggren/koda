"""Tests for the Bar component: joining, spacing, and truncation."""

from __future__ import annotations

from prompt_toolkit.layout import to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition

from koda_tui.appearance import Tokens
from koda_tui.ui.components import Bar


def _cells(bar: Bar, width: int) -> list[tuple[str, str]]:
    """Each cell of the rendered bar as (character, style)."""
    screen = Screen()
    to_container(bar).write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(xpos=0, ypos=0, width=width, height=1),
        parent_style="",
        erase_bg=False,
        z_index=None,
    )
    return [(screen.data_buffer[0][x].char, screen.data_buffer[0][x].style) for x in range(width)]


def _line(left: list[str], right: list[str], width: int) -> str:
    bar = Bar(
        lambda: [[(Tokens.Text.DEFAULT, text)] for text in left],
        lambda: [[(Tokens.Text.DEFAULT, text)] for text in right],
    )
    return "".join(char for char, _ in _cells(bar, width))


def test_sides_are_joined_and_pushed_apart_within_edge_margins() -> None:
    assert _line(["a", "b"], ["c", "d"], width=20) == " a · b" + " " * 8 + "c · d "


def test_left_side_is_cut_short_when_space_runs_out() -> None:
    assert _line(["workspace", "model"], ["ready"], width=20) == " workspa... · ready "


def test_right_side_fills_first() -> None:
    assert _line(["workspace"], ["press ctrl+c"], width=20).endswith(" press ctrl+c ")


def test_crowded_sides_keep_a_divider_even_when_nothing_is_cut() -> None:
    assert _line(["workspace"], ["ready"], width=19) == " workspace · ready "


def test_the_ellipsis_follows_the_cut_text_and_the_divider_stays_muted() -> None:
    bar = Bar(
        lambda: [[(Tokens.Text.WARNING, "medium thinking")]],
        lambda: [[(Tokens.Text.DEFAULT, "ready")]],
    )
    cells = _cells(bar, width=16)
    assert "".join(char for char, _ in cells) == " med... · ready "
    ellipsis_styles = {style for _, style in cells[4:7]}
    assert all(Tokens.Text.WARNING in style for style in ellipsis_styles)
    _, divider_style = cells[8]
    assert Tokens.Text.MUTED in divider_style
    assert Tokens.Text.WARNING not in divider_style
