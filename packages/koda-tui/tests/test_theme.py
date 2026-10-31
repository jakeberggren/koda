import pytest
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.styles import Attrs
from pydantic import ValidationError

from koda_tui.app.input import (
    OSC11_RESPONSE_KEY,
    KodaVt100Input,
    _FocusInputParser,
    _Osc11InputParser,
)
from koda_tui.design import THEMES, Theme, style_for
from koda_tui.osc import (
    RGBColor,
    parse_osc11,
)
from koda_tui.settings import TuiSettings


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
    input_._buffer = []
    input_._osc11_parser = _Osc11InputParser()
    input_._focus_parser = _FocusInputParser()
    input_.vt100_parser = Vt100Parser(input_._buffer.append)
    return input_


def _feed_test_input(input_: KodaVt100Input, data: str) -> None:
    input_._feed_text_with_terminal_events(data)  # noqa: SLF001


def _key_presses(input_: KodaVt100Input) -> list[KeyPress]:
    return input_._buffer  # noqa: SLF001


def _attrs(setting: str, terminal_background: RGBColor | None, style_class: str) -> Attrs:
    return style_for(setting, terminal_background).get_attrs_for_style_str(f"class:{style_class}")


def test_auto_theme_derives_surface_from_dark_terminal_background() -> None:
    assert _attrs("auto", (0, 0, 128), "message.user").bgcolor == "202090"
    assert _attrs("auto", (0, 0, 128), "pygments.keyword").color == "ansibrightblue"


def test_auto_theme_switches_to_light_theme_on_light_terminal_background() -> None:
    assert _attrs("auto", (250, 250, 240), "message.user").bgcolor == "dbdbd2"
    assert _attrs("auto", (250, 250, 240), "pygments.keyword").color == "ansiblue"


def test_auto_theme_falls_back_to_dark_without_osc_11() -> None:
    assert _attrs("auto", None, "input-area").bgcolor == "434343"


@pytest.mark.parametrize(
    ("setting", "terminal_background", "surface"),
    [
        ("terminal-dark", (255, 255, 255), "434343"),
        ("terminal-light", (0, 0, 0), "dcdcdc"),
        ("terminal-dark", (0, 0, 128), "202090"),
    ],
)
def test_terminal_theme_derives_surface_only_from_matching_background(
    setting: str,
    terminal_background: RGBColor,
    surface: str,
) -> None:
    assert _attrs(setting, terminal_background, "input-area").bgcolor == surface


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("auto", "auto"),
        ("terminal-dark", "terminal-dark"),
        ("dark", "terminal-dark"),
        ("light", "terminal-light"),
    ],
)
def test_theme_setting_accepts_registered_and_legacy_names(value: str, expected: str) -> None:
    assert TuiSettings(theme=value).theme == expected


def test_theme_setting_rejects_unknown_theme() -> None:
    with pytest.raises(ValidationError, match="Input should be one of 'auto', 'terminal-dark'"):
        TuiSettings(theme="solarized")


@pytest.mark.parametrize("theme", THEMES.values(), ids=lambda theme: theme.name)
def test_selection_uses_theme_accent(theme: Theme) -> None:
    attrs = _attrs(theme.name, None, "palette.selected")

    assert (attrs.bgcolor, attrs.color) == (theme.accent, theme.on_accent)


def test_syntax_child_classes_reset_inherited_dim() -> None:
    assert _attrs("terminal-dark", None, "pygments.comment").dim
    assert not _attrs("terminal-dark", None, "pygments.comment.preproc").dim
