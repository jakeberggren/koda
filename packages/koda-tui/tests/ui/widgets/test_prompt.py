"""Tests for the Prompt widget beside content taller than one row."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.layout import to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition

from koda_tui.appearance import Tokens
from koda_tui.state import AppState
from koda_tui.views.composer import Composer

WIDTH = 30


def _screen(composer: Composer) -> tuple[Screen, int]:
    container = to_container(composer)
    height = container.preferred_height(WIDTH, 20).preferred
    screen = Screen()
    container.write_to_screen(
        screen,
        MouseHandlers(),
        WritePosition(0, 0, WIDTH, height),
        "",
        erase_bg=False,
        z_index=None,
    )
    return screen, height


async def test_prompt_column_keeps_the_surface_beside_several_lines() -> None:
    composer = Composer(AppState(workspace_root=Path()))
    composer.buffer.text = "first\nsecond\nthird"

    screen, height = _screen(composer)
    prompt_rows = [screen.data_buffer[y] for y in range(height)]

    assert prompt_rows[1][1].char == "❯"  # noqa: RUF001 - the prompt glyph
    assert all(Tokens.Surface.RAISED in row[1].style for row in prompt_rows)


async def test_prompt_stays_one_column_wide() -> None:
    composer = Composer(AppState(workspace_root=Path()))
    composer.buffer.text = "hello"

    screen, _ = _screen(composer)

    assert "".join(screen.data_buffer[1][x].char for x in range(9)) == " ❯ hello "  # noqa: RUF001
