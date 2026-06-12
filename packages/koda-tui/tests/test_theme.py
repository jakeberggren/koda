from __future__ import annotations

import koda_tui.theme as theme_module
from koda_tui.theme import _parse_osc_11_response, resolve_theme


def test_resolve_theme_returns_explicit_theme() -> None:
    assert resolve_theme("dark") == "dark"
    assert resolve_theme("light") == "light"


def test_resolve_theme_auto_uses_detected_theme(monkeypatch) -> None:

    monkeypatch.setattr(theme_module, "detect_terminal_theme", lambda: "light")
    assert resolve_theme("auto") == "light"

    monkeypatch.setattr(theme_module, "detect_terminal_theme", lambda: "dark")
    assert resolve_theme("auto") == "dark"


def test_resolve_theme_auto_falls_back_to_dark(monkeypatch) -> None:

    monkeypatch.setattr(theme_module, "detect_terminal_theme", lambda: None)
    assert resolve_theme("auto") == "dark"


def test_parse_osc_11_response_detects_background_brightness() -> None:
    assert _parse_osc_11_response("\x1b]11;rgb:ffff/ffff/ffff\x1b\\") == "light"
    assert _parse_osc_11_response("\x1b]11;rgb:0000/0000/0000\x1b\\") == "dark"
    assert _parse_osc_11_response("\x1b]11;rgb:ff/ff/ff\x07") == "light"
    assert _parse_osc_11_response("no response") is None
