import pytest
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.key_binding.key_processor import KeyPress

from koda_tui.app.input import (
    OSC11_RESPONSE_KEY,
    KodaVt100Input,
    _FocusInputParser,
    _Osc11InputParser,
)
from koda_tui.osc import (
    RGBColor,
    parse_osc11,
)
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


def test_runtime_osc_11_response_routes_through_prompt_toolkit() -> None:
    response = "\x1b]11;rgb:ffff/ffff/ffff\x1b\\"
    input_ = _make_koda_input_for_parser_test()

    _feed_test_input(input_, response)

    key_presses = _key_presses(input_)
    assert len(key_presses) == 1
    assert key_presses[0].key == OSC11_RESPONSE_KEY
    assert key_presses[0].data == response


def test_runtime_osc_11_input_does_not_capture_plain_escape() -> None:
    input_ = _make_koda_input_for_parser_test()

    _feed_test_input(input_, "\x1b")
    input_.vt100_parser.flush()

    key_presses = _key_presses(input_)
    assert len(key_presses) == 1
    assert key_presses[0].key == "escape"


def test_runtime_osc_11_input_preserves_trailing_input() -> None:
    response = "\x1b]11;rgb:ffff/ffff/ffff\x1b\\"
    input_ = _make_koda_input_for_parser_test()

    _feed_test_input(input_, response + "a")

    assert [key_press.key for key_press in _key_presses(input_)] == [
        OSC11_RESPONSE_KEY,
        "a",
    ]


def _make_koda_input_for_parser_test() -> KodaVt100Input:
    input_ = object.__new__(KodaVt100Input)
    input_._buffer = []  # noqa: SLF001
    input_._osc11_parser = _Osc11InputParser()  # noqa: SLF001
    input_._focus_parser = _FocusInputParser()  # noqa: SLF001
    input_.vt100_parser = Vt100Parser(input_._buffer.append)  # noqa: SLF001
    return input_


def _feed_test_input(input_: KodaVt100Input, data: str) -> None:
    input_._feed_text_with_terminal_events(data)  # noqa: SLF001


def _key_presses(input_: KodaVt100Input) -> list[KeyPress]:
    return input_._buffer  # noqa: SLF001


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
