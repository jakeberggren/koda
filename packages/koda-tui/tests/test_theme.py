import pytest

from koda_tui.osc import RGBColor, parse_osc11
from koda_tui.theme import TerminalTheme, ThemeSetting, resolve_theme


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("\x1b]11;rgb:1234/8080/ffff\x1b\\", (18, 128, 255)),
        ("\x1b]11;rgb:ffff/ffff/ffff\x1b\\", (255, 255, 255)),
        ("\x1b]11;rgb:0000/0000/0000\x1b\\", (0, 0, 0)),
        ("\x1b]11;rgb:ff/ff/ff\x07", (255, 255, 255)),
        ("no response", None),
    ],
)
def test_parse_osc_11_response(response: str, expected: RGBColor | None) -> None:
    assert parse_osc11(response) == expected


def test_resolve_theme_uses_detected_background() -> None:
    assert resolve_theme("auto", (0, 0, 128)) == TerminalTheme(
        theme="dark",
        surface=(32, 32, 144),
    )


def test_resolve_theme_falls_back_without_osc_11() -> None:
    assert resolve_theme("auto", None) == TerminalTheme(
        theme="dark",
        surface=(67, 67, 67),
    )


@pytest.mark.parametrize(
    ("theme", "terminal_background", "expected"),
    [
        ("dark", (255, 255, 255), TerminalTheme(theme="dark", surface=(67, 67, 67))),
        ("light", (0, 0, 0), TerminalTheme(theme="light", surface=(220, 220, 220))),
    ],
)
def test_manual_theme_uses_fallback_surface(
    theme: ThemeSetting,
    terminal_background: RGBColor,
    expected: TerminalTheme,
) -> None:
    assert resolve_theme(theme, terminal_background) == expected
