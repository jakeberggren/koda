from __future__ import annotations

from copy import replace
from typing import TYPE_CHECKING

import pytest

from koda_tui.settings import Settings, SettingsError

if TYPE_CHECKING:
    from pathlib import Path


def test_without_a_file_the_settings_are_the_defaults(tmp_path: Path) -> None:
    assert Settings.load(tmp_path / "settings.json") == Settings()


def test_saved_settings_load_again(tmp_path: Path) -> None:
    path = tmp_path / "koda" / "settings.json"
    settings = replace(Settings(), model="gpt-5.5", theme="terminal-dark", queue_inputs=False)

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
        '{"theme": "neon", "web_search": "maybe", "not_a_setting": 1}', encoding="utf-8"
    )

    with pytest.raises(SettingsError) as exc_info:
        Settings.load(path)

    problems = str(exc_info.value).splitlines()[1:]
    assert [problem.split(":")[0] for problem in problems] == [
        "- web_search",
        "- theme",
        "- not_a_setting",
    ]
    assert "Input should be one of 'auto', 'terminal-dark', 'terminal-light'" in problems[1]
