"""Tests for the terminal protocol: focus reporting, and the background colour."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input.vt100_parser import Vt100Parser

from koda_tui.terminal.protocol import (
    FOCUS_REPORTING_DISABLE,
    FOCUS_REPORTING_ENABLE,
    OSC11_QUERY,
    Terminal,
    TerminalInput,
    _FocusInputParser,
    _Osc11InputParser,
    parse_osc11,
)

if TYPE_CHECKING:
    from prompt_toolkit.key_binding.key_processor import KeyPress

    from koda_tui.appearance import RGBColor

WHITE = "\x1b]11;rgb:ffff/ffff/ffff\x1b\\"


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


class _Input:
    """A TerminalInput fed by hand, recording its callbacks and keys."""

    def __init__(self) -> None:
        self.focus_ins = 0
        self.backgrounds: list[RGBColor] = []
        self.input = object.__new__(TerminalInput)
        self.input._on_focus_in = self._focus_in  # noqa: SLF001
        self.input._on_background = self.backgrounds.append  # noqa: SLF001
        self.input._buffer = []  # noqa: SLF001
        self.input._osc11_parser = _Osc11InputParser()  # noqa: SLF001
        self.input._focus_parser = _FocusInputParser()  # noqa: SLF001
        self.input.vt100_parser = Vt100Parser(self.input._buffer.append)  # noqa: SLF001

    def _focus_in(self) -> None:
        self.focus_ins += 1

    def feed(self, data: str) -> None:
        self.input._feed_text_with_terminal_events(data)  # noqa: SLF001

    @property
    def keys(self) -> list[KeyPress]:
        return self.input._buffer  # noqa: SLF001


def test_background_reply_goes_to_its_callback_not_the_keys() -> None:
    terminal = _Input()
    terminal.feed(WHITE)
    assert terminal.backgrounds == [(255, 255, 255)]
    assert terminal.keys == []


def test_background_reply_keeps_the_input_after_it() -> None:
    terminal = _Input()
    terminal.feed(WHITE + "a")
    assert terminal.backgrounds == [(255, 255, 255)]
    assert [key.key for key in terminal.keys] == ["a"]


def test_plain_escape_is_still_a_key() -> None:
    terminal = _Input()
    terminal.feed("\x1b")
    terminal.input.vt100_parser.flush()
    assert [key.key for key in terminal.keys] == ["escape"]


def test_focus_in_goes_to_its_callback_and_focus_out_is_dropped() -> None:
    terminal = _Input()
    terminal.feed("\x1b[Ia\x1b[O")
    assert terminal.focus_ins == 1
    assert [key.key for key in terminal.keys] == ["a"]


def _written(output: Mock) -> list:
    return output.write_raw.call_args_list


def test_focus_reporting_turns_on_once_and_off_on_the_final_render() -> None:
    output = Mock()
    terminal = Terminal()
    running, done = Mock(is_done=False), Mock(is_done=True)
    with create_app_session(output=output):
        for app in (running, running, done, done):
            terminal.after_render(app)
    assert _written(output) == [
        call(FOCUS_REPORTING_ENABLE),
        call(OSC11_QUERY),
        call(FOCUS_REPORTING_DISABLE),
    ]


@pytest.mark.parametrize("rendered", [True, False])
def test_close_turns_focus_reporting_off_only_if_on(*, rendered: bool) -> None:
    output = Mock()
    terminal = Terminal()
    with create_app_session(output=output):
        if rendered:
            terminal.after_render(Mock(is_done=False))
            output.reset_mock()
        terminal.close()
    assert _written(output) == ([call(FOCUS_REPORTING_DISABLE)] if rendered else [])


def test_ask_background_writes_the_query() -> None:
    output = Mock()
    with create_app_session(output=output):
        Terminal().ask_background()
    assert _written(output) == [call(OSC11_QUERY)]
