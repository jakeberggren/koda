"""Tests for the exit prompt: a second Ctrl+C within the timeout exits."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from koda_tui.app.exit import ExitPrompt

if TYPE_CHECKING:
    from koda_tui.state import AppState


def _prompt(state: AppState, timeout: float = 0.01) -> ExitPrompt:
    return ExitPrompt(state, invalidate=lambda: None, timeout=timeout)


async def test_first_ctrl_c_asks_and_second_confirms(state: AppState) -> None:
    prompt = _prompt(state)
    assert prompt.confirm() is False
    assert state.exit_requested
    assert prompt.confirm() is True
    assert not state.exit_requested


async def test_the_ask_goes_away_after_the_timeout(state: AppState) -> None:
    prompt = _prompt(state)
    prompt.confirm()

    await asyncio.sleep(0.02)

    assert not state.exit_requested
    assert prompt.confirm() is False


async def test_a_confirmed_exit_cancels_the_timeout(state: AppState) -> None:
    prompt = _prompt(state)
    prompt.confirm()
    assert prompt.confirm() is True
    state.exit_requested = True  # As if asked again after confirming.
    await asyncio.sleep(0.02)
    assert state.exit_requested  # The old timer didn't fire.
