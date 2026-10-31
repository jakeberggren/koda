"""Tests for the status bar's segments."""

# ruff: noqa: SLF001 - segment functions are module-private

from __future__ import annotations

from pathlib import Path

import pytest
from prompt_toolkit.formatted_text import fragment_list_to_text

from koda.llm import ModelDefinition, ThinkingOption
from koda.messages import TokenUsage
from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui.appearance import Tokens
from koda_tui.state import AppState, ResponsePhase
from koda_tui.views import status


def _texts(segments) -> list[str]:
    return [fragment_list_to_text(segment) for segment in segments]


def _state(**fields) -> AppState:
    return AppState(workspace_root=Path.home() / "dev" / "koda", **fields)


def test_left_shows_workspace_model_thinking_and_usage() -> None:
    model = ModelDefinition(
        id="m",
        name="Model",
        provider="provider",
        context_window=1000,
        thinking_options=[],
    )
    usage = TokenUsage(input_tokens=120, output_tokens=0)
    state = _state(
        active_model=model,
        thinking=ThinkingOption(id="medium", label="Medium"),
        context_window=1000,
        usage=usage,
        total_usage=TokenUsage(input_tokens=34, output_tokens=15_900),
    )
    assert _texts(status._left(state)) == [
        "~/dev/koda",
        "provider · Model",
        "medium",
        f"ctx {usage.context_window_percentage(1000)}%",
        "34 in",
        "15.9k out",
    ]


def test_workspace_outside_home_shows_its_name() -> None:
    assert _texts([status._location(AppState(workspace_root=Path("/srv/app")))]) == ["~/app"]


def test_right_shows_hints_warning_and_activity() -> None:
    state = _state(thinking_supported=True, warnings=["Config has unknown keys"])
    assert _texts(status._right(state)) == [
        "ctrl+t thinking",
        "ctrl+p/k palette",
        "Config has unknown keys",
        "ready",
    ]


@pytest.mark.parametrize(
    ("fields", "text"),
    [
        ({"exit_requested": True}, "press ctrl+c again to exit"),
        ({"is_thinking": True}, "thinking"),
        ({"response_phase": ResponsePhase.RESPONDING}, "responding"),
        ({"response_phase": ResponsePhase.WORKING}, "working"),
        ({}, "ready"),
    ],
)
def test_activity_follows_the_response(fields: dict, text: str) -> None:
    assert status._activity(_state(**fields)) == [(Tokens.Text.ACCENT, text)]


def test_activity_warns_when_the_service_is_not_ready() -> None:
    not_ready = next(code for code in ServiceStatusCode if code is not ServiceStatusCode.READY)
    state = _state(service_status=ServiceStatus(code=not_ready, summary="No provider configured"))
    assert status._activity(state) == [(Tokens.Text.WARNING, "No provider configured")]


@pytest.mark.parametrize(
    ("count", "text"),
    [(950, "950"), (1_000, "1k"), (15_900, "15.9k"), (1_200_000, "1.2M")],
)
def test_compact_token_counts(count: int, text: str) -> None:
    assert status._compact(count) == text
