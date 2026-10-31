"""Tests for the status bar's segments."""

# ruff: noqa: SLF001 - segment functions are module-private

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from prompt_toolkit.formatted_text import fragment_list_to_text

from koda.llm import ModelDefinition, ThinkingOption
from koda.messages import TokenUsage
from koda.tools import ToolCall
from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui.appearance import Tokens
from koda_tui.state import AppState, AssistantMessage, ToolMessage, Usage, UserMessage
from koda_tui.views import status

_CALL = ToolCall(tool_name="bash", arguments={}, call_id="call_1")


def _texts(segments) -> list[str]:
    return [fragment_list_to_text(segment) for segment in segments]


def _state(state: AppState, **fields) -> AppState:
    """``state`` in a workspace under the home directory, with ``fields`` changed."""
    return replace(state, workspace=Path.home() / "dev" / "koda", **fields)


def test_left_shows_workspace_model_thinking_and_usage(state: AppState) -> None:
    model = ModelDefinition(
        id="m",
        name="Model",
        provider="provider",
        context_window=1000,
        thinking_options=[],
    )
    usage = TokenUsage(input_tokens=120, output_tokens=0)
    state = _state(
        state,
        active_model=model,
        thinking=ThinkingOption(id="medium", label="Medium"),
        usage=Usage(latest=usage, total=TokenUsage(input_tokens=34, output_tokens=15_900)),
    )
    assert _texts(status._left(state)) == [
        "~/dev/koda",
        "provider · Model",
        "medium",
        f"ctx {usage.context_window_percentage(1000)}%",
        "34 in",
        "15.9k out",
    ]


def test_workspace_outside_home_shows_its_full_path(state: AppState) -> None:
    assert _texts([status._location(replace(state, workspace=Path("/srv/app")))]) == ["/srv/app"]


def test_home_workspace_shows_a_tilde(state: AppState) -> None:
    assert _texts([status._location(replace(state, workspace=Path.home()))]) == ["~"]


def test_right_shows_hints_warning_and_activity(state: AppState) -> None:
    model = ModelDefinition(
        id="m",
        name="Model",
        provider="provider",
        thinking_options=[ThinkingOption(id="medium", label="Medium")],
    )
    state = _state(state, active_model=model, warnings=["Config has unknown keys"])
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
        ({"responding": True, "messages": [AssistantMessage("", "hmm")]}, "thinking"),
        ({"responding": True, "messages": [AssistantMessage("Hi")]}, "responding"),
        ({"responding": True, "messages": [UserMessage("hi")]}, "working"),
        (
            {"responding": True, "messages": [UserMessage("hi"), ToolMessage(_CALL)]},
            "running tools",
        ),
        ({}, "ready"),
    ],
)
def test_activity_follows_the_response(state: AppState, fields: dict, text: str) -> None:
    assert status._activity(_state(state, **fields)) == [(Tokens.Text.ACCENT, text)]


def test_activity_warns_when_the_service_is_not_ready(state: AppState) -> None:
    not_ready = next(code for code in ServiceStatusCode if code is not ServiceStatusCode.READY)
    state = _state(
        state, service_status=ServiceStatus(code=not_ready, summary="No provider configured")
    )
    assert status._activity(state) == [(Tokens.Text.WARNING, "No provider configured")]


@pytest.mark.parametrize(
    ("count", "text"),
    [(950, "950"), (1_000, "1k"), (15_900, "15.9k"), (1_200_000, "1.2M")],
)
def test_compact_token_counts(count: int, text: str) -> None:
    assert status._compact(count) == text
