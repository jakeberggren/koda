"""Tests for the TUI settings."""

import pytest
from pydantic import ValidationError

from koda_tui.settings import TuiSettings


@pytest.mark.parametrize("value", ["auto", "terminal-dark", "terminal-light"])
def test_theme_setting_accepts_auto_and_registered_themes(value: str) -> None:
    assert TuiSettings(theme=value).theme == value


@pytest.mark.parametrize("value", ["solarized", "dark"])
def test_theme_setting_rejects_unknown_theme(value: str) -> None:
    with pytest.raises(ValidationError, match="Input should be one of 'auto', 'terminal-dark'"):
        TuiSettings(theme=value)
