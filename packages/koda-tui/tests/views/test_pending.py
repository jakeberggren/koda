"""Tests for the pending (queued) messages shown while a response runs."""

from __future__ import annotations

from pathlib import Path

from prompt_toolkit.layout import to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition

from koda_tui.state import AppState
from koda_tui.views import PendingMessages


def _rows(pending: list[str], width: int = 40) -> list[str]:
    container = to_container(
        PendingMessages(AppState(workspace_root=Path("/tmp"), pending_inputs=pending)),
    )
    height = container.preferred_height(width, 20).preferred
    screen = Screen()
    if height:
        container.write_to_screen(
            screen,
            MouseHandlers(),
            WritePosition(xpos=0, ypos=0, width=width, height=height),
            parent_style="",
            erase_bg=False,
            z_index=None,
        )
    return [
        "".join(screen.data_buffer[y][x].char for x in range(width)).rstrip() for y in range(height)
    ]


def test_hidden_when_nothing_is_queued() -> None:
    assert _rows([]) == []


def test_shows_the_count_then_the_latest_three_indented() -> None:
    rows = _rows(["one", "two", "three", "four"], width=80)
    assert rows == [
        "  4 messages queued (esc to send now, alt/option-up to edit)",
        "  two",
        "  three",
        "  four",
    ]


def test_long_messages_wrap_by_word() -> None:
    rows = _rows(["keep the tests green while refactoring"], width=24)
    assert rows[-2:] == ["  keep the tests green", "  while refactoring"]
