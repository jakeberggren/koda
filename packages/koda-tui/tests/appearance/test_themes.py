"""Tests for the themes: the auto theme, the terminal's background, and colours."""

import pytest
from prompt_toolkit.styles import Attrs

from koda_tui.appearance import Appearance, RGBColor, Tokens


def _attrs(setting: str, terminal_background: RGBColor | None, style: str) -> Attrs:
    appearance = Appearance(setting)
    appearance.terminal_background = terminal_background
    return appearance.style.get_attrs_for_style_str(style)


def test_auto_theme_derives_surface_from_dark_terminal_background() -> None:
    assert _attrs("auto", RGBColor(0, 0, 128), Tokens.Surface.RAISED).bgcolor == "202090"
    assert _attrs("auto", RGBColor(0, 0, 128), "class:pygments.keyword").color == "ansibrightblue"


def test_auto_theme_switches_to_light_theme_on_light_terminal_background() -> None:
    assert _attrs("auto", RGBColor(250, 250, 240), Tokens.Surface.RAISED).bgcolor == "dbdbd2"
    assert _attrs("auto", RGBColor(250, 250, 240), "class:pygments.keyword").color == "ansiblue"


def test_auto_theme_falls_back_to_dark_without_osc_11() -> None:
    assert _attrs("auto", None, Tokens.Surface.RAISED).bgcolor == "434343"


@pytest.mark.parametrize(
    ("setting", "terminal_background", "surface"),
    [
        ("terminal-dark", RGBColor(255, 255, 255), "434343"),
        ("terminal-light", RGBColor(0, 0, 0), "dcdcdc"),
        ("terminal-dark", RGBColor(0, 0, 128), "202090"),
    ],
)
def test_terminal_theme_derives_surface_only_from_matching_background(
    setting: str,
    terminal_background: RGBColor,
    surface: str,
) -> None:
    assert _attrs(setting, terminal_background, Tokens.Surface.RAISED).bgcolor == surface


def test_rgb_color_blends_toward_a_target() -> None:
    assert RGBColor(0, 0, 128).blend(RGBColor(255, 255, 255), 0.125) == RGBColor(32, 32, 144)
    assert RGBColor(32, 32, 144).hex == "#202090"


@pytest.mark.parametrize(
    ("color", "is_light"),
    [(RGBColor(0, 0, 0), False), (RGBColor(0, 0, 128), False), (RGBColor(250, 250, 240), True)],
)
def test_rgb_color_reads_as_light_or_dark(color: RGBColor, *, is_light: bool) -> None:
    assert color.is_light is is_light
