"""Protocol: the terminal's focus and background colour, beyond keys.

``Terminal`` writes the requests; ``TerminalInput`` reads the replies from the input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from prompt_toolkit.application.current import get_app_session
from prompt_toolkit.input.vt100 import Vt100Input

from koda_tui.appearance import RGBColor

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit import Application
    from prompt_toolkit.key_binding.key_processor import KeyPress

OSC_BEL = "\x07"
OSC_STRING_TERMINATOR = "\x1b\\"
OSC11_QUERY = "\033]11;?\033\\"
FOCUS_REPORTING_ENABLE = "\033[?1004h"
FOCUS_REPORTING_DISABLE = "\033[?1004l"
FOCUS_IN = "\x1b[I"
FOCUS_OUT = "\x1b[O"

# Regex matching any OSC 11 terminal background color response.
OSC11_RESPONSE_RE = re.compile(
    "^"
    + re.escape("\x1b]11;rgb:")
    + r"([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})"
    + r"(?:"
    + re.escape(OSC_STRING_TERMINATOR)
    + "|"
    + re.escape(OSC_BEL)
    + r")\Z"
)
OSC11_RESPONSE_START = "\x1b]11;rgb:"

# Regex matching any valid prefix of an OSC 11 response after the fixed start.
# The final string terminator can arrive as "\x1b\\" split across input reads.
OSC11_PREFIX_RE = re.compile(
    "^"
    + re.escape(OSC11_RESPONSE_START)
    + r"[0-9a-fA-F]{0,4}(?:/[0-9a-fA-F]{0,4}"
    + r"(?:/[0-9a-fA-F]{0,4}(?:\x1b?)?)?)?\Z"
)


def parse_osc11(response: str) -> RGBColor | None:
    """Parse an OSC 11 terminal background color response."""
    match = OSC11_RESPONSE_RE.search(response)
    if not match:
        return None

    components: list[int] = []
    for value in match.groups():
        max_value = (16 ** len(value)) - 1
        components.append(round(int(value, 16) * 255 / max_value))
    return RGBColor(*components)


def is_osc11_response_prefix(prefix: str) -> bool:
    """Return whether text is a partial OSC 11 response."""
    return (
        len(prefix) > 1
        and parse_osc11(prefix) is None
        and (OSC11_RESPONSE_START.startswith(prefix) or bool(OSC11_PREFIX_RE.match(prefix)))
    )


_FOCUS_SEQUENCES = (FOCUS_IN, FOCUS_OUT)


@dataclass(frozen=True)
class _InputChunk:
    text: str | None = None
    osc11_response: str | None = None


@dataclass(frozen=True)
class _FocusInputChunk:
    text: str | None = None
    sequence: str | None = None  # FOCUS_IN or FOCUS_OUT.


class _Osc11InputParser:
    """Extract OSC 11 responses from terminal input text."""

    def __init__(self) -> None:
        self._pending = ""

    @staticmethod
    def _osc11_start_suffix(data: str) -> str:
        for start in range(max(0, len(data) - len(OSC11_RESPONSE_START) + 1), len(data)):
            suffix = data[start:]
            if len(suffix) > 1 and OSC11_RESPONSE_START.startswith(suffix):
                return suffix
        return ""

    @staticmethod
    def _split_osc11_response(data: str) -> tuple[str, str] | None:
        terminators = [index + len(OSC_BEL) for index, char in enumerate(data) if char == OSC_BEL]
        terminators.extend(
            index + len(OSC_STRING_TERMINATOR)
            for index in range(len(data) - len(OSC_STRING_TERMINATOR) + 1)
            if data[index : index + len(OSC_STRING_TERMINATOR)] == OSC_STRING_TERMINATOR
        )

        for end in sorted(terminators):
            response = data[:end]
            if parse_osc11(response) is not None:
                return (response, data[end:])
        return None

    def _consume_non_osc11_text(self, data: str) -> _InputChunk:
        suffix = self._osc11_start_suffix(data)
        if suffix:
            self._pending = suffix
            return _InputChunk(text=data[: -len(suffix)])
        return _InputChunk(text=data)

    def _consume_osc11_text(self, data: str) -> tuple[_InputChunk, str]:
        osc_response = self._split_osc11_response(data)
        if osc_response is not None:
            response, remaining = osc_response
            return (_InputChunk(osc11_response=response), remaining)

        if is_osc11_response_prefix(data):
            self._pending = data
            return (_InputChunk(), "")

        return (_InputChunk(text=data[0]), data[1:])

    def feed(self, data: str) -> list[_InputChunk]:
        data = self._pending + data
        self._pending = ""
        chunks: list[_InputChunk] = []

        while data:
            osc_start = data.find(OSC11_RESPONSE_START)
            if osc_start == -1:
                chunks.append(self._consume_non_osc11_text(data))
                break

            chunks.append(_InputChunk(text=data[:osc_start]))
            chunk, data = self._consume_osc11_text(data[osc_start:])
            chunks.append(chunk)

        return chunks

    def flush(self) -> str:
        pending = self._pending
        self._pending = ""
        return pending


class _FocusInputParser:
    """Extract terminal focus events from terminal input text."""

    def __init__(self) -> None:
        self._pending = ""

    @staticmethod
    def _focus_start_suffix(data: str) -> str:
        for start in range(max(0, len(data) - 2), len(data)):
            suffix = data[start:]
            if len(suffix) > 1 and any(
                sequence.startswith(suffix) for sequence in _FOCUS_SEQUENCES
            ):
                return suffix
        return ""

    def _consume_text(self, data: str) -> _FocusInputChunk:
        suffix = self._focus_start_suffix(data)
        if suffix:
            self._pending = suffix
            return _FocusInputChunk(text=data[: -len(suffix)])
        return _FocusInputChunk(text=data)

    def feed(self, data: str) -> list[_FocusInputChunk]:
        data = self._pending + data
        self._pending = ""
        chunks: list[_FocusInputChunk] = []

        while data:
            focus_events = [
                (index, sequence)
                for sequence in _FOCUS_SEQUENCES
                if (index := data.find(sequence)) != -1
            ]
            if not focus_events:
                chunks.append(self._consume_text(data))
                break

            index, sequence = min(focus_events)
            chunks.append(_FocusInputChunk(text=data[:index]))
            chunks.append(_FocusInputChunk(sequence=sequence))
            data = data[index + len(sequence) :]

        return chunks

    def flush(self) -> str:
        pending = self._pending
        self._pending = ""
        return pending


class Terminal:
    """Reports the terminal's focus while Koda runs, and asks for its background colour
    once at the start and whenever asked again."""

    def __init__(self) -> None:
        self._reporting_focus = False
        self._asked_background = False

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
        """Ask for the background colour; the reply comes through ``TerminalInput``."""
        self._asked_background = True
        self._write(OSC11_QUERY)

    def close(self) -> None:
        """Turn focus reporting off, if it is on."""
        if self._reporting_focus:
            self._write(FOCUS_REPORTING_DISABLE)
            self._reporting_focus = False

    @staticmethod
    def _write(sequence: str) -> None:
        output = get_app_session().output
        output.write_raw(sequence)
        output.flush()


class TerminalInput(Vt100Input):
    """Reads the terminal's replies out of the input, passing focus coming back to
    ``on_focus_in`` and the background colour to ``on_background``; everything else is
    keys for prompt_toolkit."""

    def __init__(
        self,
        stdin: TextIO,
        *,
        on_focus_in: Callable[[], None],
        on_background: Callable[[RGBColor], None],
    ) -> None:
        super().__init__(stdin)
        self._on_focus_in = on_focus_in
        self._on_background = on_background
        self._osc11_parser = _Osc11InputParser()
        self._focus_parser = _FocusInputParser()

    def _feed_text_with_focus_events(self, data: str) -> None:
        for chunk in self._focus_parser.feed(data):
            if chunk.sequence == FOCUS_IN:
                self._on_focus_in()
            elif chunk.text:
                self.vt100_parser.feed(chunk.text)

    def _feed_text_with_terminal_events(self, data: str) -> None:
        for chunk in self._osc11_parser.feed(data):
            if chunk.osc11_response is not None:
                if (background := parse_osc11(chunk.osc11_response)) is not None:
                    self._on_background(background)
            elif chunk.text:
                self._feed_text_with_focus_events(chunk.text)

    def read_keys(self) -> list[KeyPress]:
        """Read keys, taking the terminal's replies out first."""
        self._feed_text_with_terminal_events(self.stdin_reader.read())
        result = self._buffer
        self._buffer = []
        return result

    def flush_keys(self) -> list[KeyPress]:
        """Flush pending partial replies and prompt_toolkit input."""
        self._feed_text_with_focus_events(self._osc11_parser.flush())
        self.vt100_parser.feed(self._focus_parser.flush())
        return super().flush_keys()
