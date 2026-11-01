"""Tests for the pending (queued) messages shown while a response runs."""

from __future__ import annotations

from prompt_toolkit.layout import to_container
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition

from koda_tui.state import AppState, PendingInput
from koda_tui.views import PendingMessages


def _rows(state: AppState, pending: list[PendingInput], width: int = 40) -> list[str]:
    state.pending_inputs = pending
    container = to_container(PendingMessages(state))
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


def test_hidden_when_nothing_is_queued(state: AppState) -> None:
    assert _rows(state, []) == []


def test_shows_the_count_then_the_latest_three_indented(state: AppState) -> None:
    rows = _rows(state, [PendingInput(text) for text in ["one", "two", "three", "four"]], width=80)
    assert rows == [
        " 4 messages queued (esc to send now, alt+up to edit)",
        " two",
        " three",
        " four",
    ]


def test_long_messages_wrap_by_word(state: AppState) -> None:
    rows = _rows(state, [PendingInput("keep the tests green while refactoring")], width=24)
    assert rows[-2:] == [" keep the tests green", " while refactoring"]


def test_steers_are_labelled_above_the_queue(state: AppState) -> None:
    pending = [PendingInput("fix it", steer=True), PendingInput("then this")]
    assert _rows(state, pending, width=80) == [
        " steering: fix it",
        " 1 message queued (esc to send now, alt+up to edit)",
        " then this",
    ]


def test_only_steers_shows_no_queue_count(state: AppState) -> None:
    assert _rows(state, [PendingInput("fix it", steer=True)]) == [" steering: fix it"]


def test_long_steers_wrap_by_word(state: AppState) -> None:
    rows = _rows(state, [PendingInput("keep the tests green please", steer=True)], width=24)
    assert rows == [" steering: keep the", " tests green please"]
