"""Tests for the theme menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui import strings
from koda_tui.palette.menus.theme import ThemeMenu
from koda_tui.settings import Settings

if TYPE_CHECKING:
    from unittest.mock import Mock

    from tests.palette.conftest import Overlays

    from koda_tui.palette.context import PaletteContext


def test_lists_the_themes_marking_the_current_one(
    context: PaletteContext, overlays: Overlays
) -> None:
    context.state.settings = Settings(theme="terminal-light")
    ThemeMenu(context).open()
    items = overlays.stack[-1]["items"]
    assert [item.data for item in items] == ["auto", "terminal-dark", "terminal-light"]
    assert [item.current for item in items] == [False, False, True]


def test_choosing_a_theme_sets_it(context: PaletteContext, overlays: Overlays) -> None:
    ThemeMenu(context).open()
    overlays.pick(strings.Palette.Themes.DARK)
    assert context.settings.theme == "terminal-dark"


def test_choosing_the_current_theme_asks_for_the_background_again(
    context: PaletteContext, overlays: Overlays, update_settings: Mock, terminal: Mock
) -> None:
    ThemeMenu(context).open()
    overlays.pick("Auto")
    terminal.ask_background.assert_called_once_with()
    update_settings.assert_not_called()
