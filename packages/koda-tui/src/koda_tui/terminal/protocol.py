"""Protocol: the terminal's focus and background colour, beyond keys.

``Terminal`` holds the exchange: it writes the requests and reads the replies.
``TerminalInput`` hands it the input before prompt_toolkit reads the rest as keys.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, TextIO

from prompt_toolkit.application.current import get_app_session
from prompt_toolkit.input.vt100 import Vt100Input

from koda_tui.appearance import RGBColor

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit import Application
    from prompt_toolkit.input import Input
    from prompt_toolkit.key_binding.key_processor import KeyPress

OSC11_QUERY = "\x1b]11;?\x1b\\"
FOCUS_REPORTING_ENABLE = "\x1b[?1004h"
FOCUS_REPORTING_DISABLE = "\x1b[?1004l"
FOCUS_IN = "\x1b[I"
FOCUS_OUT = "\x1b[O"
OSC11_START = "\x1b]11;rgb:"

# A whole reply: focus in or out, or the background colour as hex channels, ended by
# ST (ESC \) or BEL.
_HEX = "[0-9a-fA-F]"
REPLY = re.compile(
    r"\x1b\[(?P<focus>[IO])"
    rf"|{re.escape(OSC11_START)}(?P<red>{_HEX}{{2,4}})/(?P<green>{_HEX}{{2,4}})/(?P<blue>{_HEX}{{2,4}})"
    r"(?:\x1b\\|\x07)"
)
# The start of a background colour reply cut off by the end of a read; the ST that
# ends it can be cut between its ESC and backslash.
PARTIAL_OSC11 = re.compile(
    rf"{re.escape(OSC11_START)}{_HEX}{{0,4}}(?:/{_HEX}{{0,4}}(?:/{_HEX}{{0,4}}\x1b?)?)?"
)


class Terminal:
    """Koda's exchange with the terminal beyond keys. While Koda runs, the terminal
    reports focus; Koda asks for its background colour at the start, whenever focus
    comes back, and whenever asked, and passes each colour to ``on_background``.

    ``feed`` takes the replies out of the input and returns the rest, the keys. A reply
    can arrive split across reads, so the end of a read that could still become one is
    held back until the next read, or until ``flush``.
    """

    def __init__(self, *, on_background: Callable[[RGBColor], None]) -> None:
        self._on_background = on_background
        self._reporting_focus = False
        self._asked_background = False
        self._held = ""

    def input(self) -> Input:
        """The session's input, with this terminal's replies taken out when it is a real
        terminal."""
        session_input = get_app_session().input
        if not isinstance(session_input, Vt100Input):
            return session_input
        return TerminalInput(session_input.stdin, self)

    def after_render(self, app: Application[None]) -> None:
        """Turn focus reporting on while running, and off on the final render.

        Renders happen in raw mode, so the terminal's immediate focus report isn't
        echoed onto the screen, and none leak to the shell after exit.
        """
        if app.is_done:
            self.close()
            return
        if not self._reporting_focus:
            self._write(FOCUS_REPORTING_ENABLE)
            self._reporting_focus = True
        if not self._asked_background:
            self.ask_background()

    def ask_background(self) -> None:
        """Ask for the background colour; the reply comes through ``feed``."""
        self._asked_background = True
        self._write(OSC11_QUERY)

    def close(self) -> None:
        """Turn focus reporting off, if it is on."""
        if self._reporting_focus:
            self._write(FOCUS_REPORTING_DISABLE)
            self._reporting_focus = False

    def feed(self, data: str) -> str:
        """``data`` without the replies in it, acting on each reply."""
        data, self._held = self._held + data, ""
        keys: list[str] = []
        end = 0
        for match in REPLY.finditer(data):
            keys.append(data[end : match.start()])
            self._reply(match)
            end = match.end()
        rest = data[end:]
        self._held = _unfinished(rest)
        keys.append(rest[: len(rest) - len(self._held)])
        return "".join(keys)

    def flush(self) -> str:
        """What was held back, as keys: no reply came of it."""
        held, self._held = self._held, ""
        return held

    def _reply(self, match: re.Match[str]) -> None:
        """Ask for the background again when focus comes back, and pass a colour on;
        focus going away needs nothing."""
        match match["focus"]:
            case "I":
                self.ask_background()
            case None:
                channels = (match[name] for name in ("red", "green", "blue"))
                self._on_background(RGBColor(*(_channel(value) for value in channels)))

    @staticmethod
    def _write(sequence: str) -> None:
        output = get_app_session().output
        output.write_raw(sequence)
        output.flush()


def _channel(value: str) -> int:
    """A hex channel of 2 to 4 digits, scaled to 0-255."""
    return round(int(value, 16) * 255 / (16 ** len(value) - 1))


def _unfinished(text: str) -> str:
    """The end of ``text`` that could still become a reply, from an ESC. That includes
    a lone ESC, which ``flush`` lets through in time to be the Escape key: prompt_toolkit
    holds a lone ESC until it flushes the keys anyway."""
    for index, char in enumerate(text):
        if char == "\x1b" and _could_become_reply(text[index:]):
            return text[index:]
    return ""


def _could_become_reply(text: str) -> bool:
    return any(start.startswith(text) for start in (FOCUS_IN, FOCUS_OUT, OSC11_START)) or bool(
        PARTIAL_OSC11.fullmatch(text)
    )


class TerminalInput(Vt100Input):
    """prompt_toolkit's input from the terminal, with ``terminal``'s replies taken out
    before the rest is read as keys."""

    def __init__(self, stdin: TextIO, terminal: Terminal) -> None:
        super().__init__(stdin)
        self._terminal = terminal

    def read_keys(self) -> list[KeyPress]:
        """Read keys, taking the terminal's replies out first."""
        self.vt100_parser.feed(self._terminal.feed(self.stdin_reader.read()))
        result = self._buffer
        self._buffer = []
        return result

    def flush_keys(self) -> list[KeyPress]:
        """Pass what was held back as a possible reply to the keys, then flush them."""
        self.vt100_parser.feed(self._terminal.flush())
        return super().flush_keys()
