"""Tests for the terminal protocol: focus reporting, the background colour, and taking
the terminal's replies out of the keys."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, call

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input.vt100_parser import Vt100Parser

from koda_tui.appearance import RGBColor
from koda_tui.terminal.protocol import (
    FOCUS_REPORTING_DISABLE,
    FOCUS_REPORTING_ENABLE,
    OSC11_QUERY,
    Terminal,
    TerminalInput,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

WHITE = "\x1b]11;rgb:ffff/ffff/ffff\x1b\\"


@pytest.fixture
def output() -> Iterator[Mock]:
    """The output the terminal writes to."""
    output = Mock()
    with create_app_session(output=output):
        yield output


@pytest.fixture
def backgrounds() -> list[RGBColor]:
    return []


@pytest.fixture
def terminal(backgrounds: list[RGBColor]) -> Terminal:
    return Terminal(on_background=backgrounds.append)


def _written(output: Mock) -> list:
    return output.write_raw.call_args_list


@pytest.mark.parametrize(
    ("reply", "color"),
    [
        ("\x1b]11;rgb:1234/8080/ffff\x1b\\", (18, 128, 255)),
        ("\x1b]11;rgb:ffff/ffff/ffff\x1b\\", (255, 255, 255)),
        ("\x1b]11;rgb:0000/0000/0000\x1b\\", (0, 0, 0)),
        ("\x1b]11;rgb:ff/ff/ff\x07", (255, 255, 255)),
    ],
)
def test_background_reply_goes_to_its_callback_not_the_keys(
    terminal: Terminal, backgrounds: list[RGBColor], reply: str, color: tuple[int, int, int]
) -> None:
    assert terminal.feed(f"a{reply}b") == "ab"
    assert backgrounds == [RGBColor(*color)]


def test_text_that_is_not_a_reply_stays_keys(
    terminal: Terminal, backgrounds: list[RGBColor]
) -> None:
    text = "no reply \x1b]11;rgb:zz/zz/zz\x07"
    assert terminal.feed(text) == text
    assert backgrounds == []


@pytest.mark.parametrize("cut", range(1, len(WHITE)))
def test_a_reply_split_across_reads_is_put_back_together(
    terminal: Terminal, backgrounds: list[RGBColor], cut: int
) -> None:
    assert terminal.feed("a" + WHITE[:cut]) == "a"
    assert terminal.feed(WHITE[cut:] + "b") == "b"
    assert backgrounds == [RGBColor(255, 255, 255)]


def test_focus_coming_back_asks_for_the_background_again(terminal: Terminal, output: Mock) -> None:
    assert terminal.feed("\x1b[Ia\x1b[O") == "a"
    assert _written(output) == [call(OSC11_QUERY)]


def test_a_split_focus_in_is_put_back_together(terminal: Terminal, output: Mock) -> None:
    assert terminal.feed("a\x1b[") == "a"
    assert terminal.feed("I") == ""
    assert _written(output) == [call(OSC11_QUERY)]


def test_what_never_became_a_reply_is_flushed_as_keys(terminal: Terminal) -> None:
    assert terminal.feed("\x1b]11;rgb:ff") == ""
    assert terminal.flush() == "\x1b]11;rgb:ff"
    assert terminal.flush() == ""


def test_a_lone_escape_is_held_back_until_flushed(terminal: Terminal) -> None:
    assert terminal.feed("a\x1b") == "a"
    assert terminal.flush() == "\x1b"


def test_focus_reporting_turns_on_once_and_off_on_the_final_render(
    terminal: Terminal, output: Mock
) -> None:
    running, done = Mock(is_done=False), Mock(is_done=True)
    for app in (running, running, done, done):
        terminal.after_render(app)
    assert _written(output) == [
        call(FOCUS_REPORTING_ENABLE),
        call(OSC11_QUERY),
        call(FOCUS_REPORTING_DISABLE),
    ]


@pytest.mark.parametrize("rendered", [True, False])
def test_close_turns_focus_reporting_off_only_if_on(
    terminal: Terminal, output: Mock, *, rendered: bool
) -> None:
    if rendered:
        terminal.after_render(Mock(is_done=False))
        output.reset_mock()
    terminal.close()
    assert _written(output) == ([call(FOCUS_REPORTING_DISABLE)] if rendered else [])


def test_ask_background_writes_the_query(terminal: Terminal, output: Mock) -> None:
    terminal.ask_background()
    assert _written(output) == [call(OSC11_QUERY)]


def _input(terminal: Terminal, data: str) -> TerminalInput:
    """A TerminalInput whose stdin has ``data`` waiting."""
    terminal_input = object.__new__(TerminalInput)
    terminal_input._terminal = terminal
    terminal_input._buffer = []
    # Looks the buffer up on each key, as Vt100Input does: read_keys replaces it.
    terminal_input.vt100_parser = Vt100Parser(lambda key: terminal_input._buffer.append(key))  # noqa: PLW0108
    terminal_input.stdin_reader = Mock(read=Mock(return_value=data))
    return terminal_input


def test_input_reads_keys_without_the_replies(
    terminal: Terminal, backgrounds: list[RGBColor]
) -> None:
    assert [key.key for key in _input(terminal, WHITE + "a").read_keys()] == ["a"]
    assert backgrounds == [RGBColor(255, 255, 255)]


def test_input_flushes_a_lone_escape_as_the_escape_key(terminal: Terminal) -> None:
    terminal_input = _input(terminal, "\x1b")
    assert terminal_input.read_keys() == []
    assert [key.key for key in terminal_input.flush_keys()] == ["escape"]
