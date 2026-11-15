from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda.llm import Model, Thinking, ThinkingOption
from koda_tui.settings import AgentSettings, Settings, SettingsError, TuiSettings

if TYPE_CHECKING:
    from pathlib import Path


def test_without_a_file_the_settings_are_the_defaults(tmp_path: Path) -> None:
    assert Settings.load(tmp_path / "settings.json") == Settings()


def test_saved_settings_load_again(tmp_path: Path) -> None:
    path = tmp_path / "koda" / "settings.json"
    settings = Settings(
        agent_settings=AgentSettings(model="gpt-5.5"),
        tui_settings=TuiSettings(theme="terminal-dark", queue_inputs=False),
    )

    settings.save(path)

    assert Settings.load(path) == settings


def test_a_file_that_isnt_json_says_where(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(SettingsError, match=f"Invalid settings in {path}"):
        Settings.load(path)


def test_every_problem_is_listed(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"tui_settings": {"theme": "neon"}, '
        '"agent_settings": {"web_search": "maybe"}, "not_a_setting": 1}',
        encoding="utf-8",
    )

    with pytest.raises(SettingsError) as exc_info:
        Settings.load(path)

    problems = str(exc_info.value).splitlines()[1:]
    assert [problem.split(":")[0] for problem in problems] == [
        "- agent_settings.web_search",
        "- tui_settings.theme",
        "- not_a_setting",
    ]
    assert "Input should be one of 'auto', 'terminal-dark', 'terminal-light'" in problems[1]


def _model() -> Model:
    return Model(
        id="m",
        name="M",
        provider="p",
        thinking=Thinking((ThinkingOption("low", "Low"), ThinkingOption("high", "High"))),
    )


def test_request_options_carry_the_agent_settings() -> None:
    settings = AgentSettings(thinking="high", web_search=True, extended_prompt_retention=True)

    options = settings.request_options(_model())

    assert (options.thinking, options.web_search, options.extended_prompt_retention) == (
        "high",
        True,
        True,
    )


def test_thinking_the_model_lacks_falls_back_to_its_first_level() -> None:
    assert AgentSettings(thinking="max").request_options(_model()).thinking == "low"
