"""Koda-specific prompt_toolkit input handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TextIO

from prompt_toolkit.input.vt100 import Vt100Input
from prompt_toolkit.key_binding.key_processor import KeyPress

from koda_tui.osc import (
    OSC11_RESPONSE_START,
    OSC_BEL,
    OSC_STRING_TERMINATOR,
    is_osc11_response_prefix,
    parse_osc11,
)

FOCUS_IN_KEY = "\ue000"
FOCUS_OUT_KEY = "\ue001"
OSC11_RESPONSE_KEY = "\ue002"
_FOCUS_SEQUENCES = {
    "\x1b[I": FOCUS_IN_KEY,
    "\x1b[O": FOCUS_OUT_KEY,
}


@dataclass(frozen=True)
class _InputChunk:
    text: str | None = None
    osc11_response: str | None = None


@dataclass(frozen=True)
class _FocusInputChunk:
    text: str | None = None
    focus_key: str | None = None
    sequence: str | None = None


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
                (index, sequence, key)
                for sequence, key in _FOCUS_SEQUENCES.items()
                if (index := data.find(sequence)) != -1
            ]
            if not focus_events:
                chunks.append(self._consume_text(data))
                break

            index, sequence, key = min(focus_events)
            chunks.append(_FocusInputChunk(text=data[:index]))
            chunks.append(_FocusInputChunk(focus_key=key, sequence=sequence))
            data = data[index + len(sequence) :]

        return chunks

    def flush(self) -> str:
        pending = self._pending
        self._pending = ""
        return pending


class KodaVt100Input(Vt100Input):
    """Vt100Input that routes Koda terminal events through prompt_toolkit key handling."""

    def __init__(self, stdin: TextIO) -> None:
        super().__init__(stdin)
        self._osc11_parser = _Osc11InputParser()
        self._focus_parser = _FocusInputParser()

    def _feed_text_with_focus_events(self, data: str) -> None:
        for chunk in self._focus_parser.feed(data):
            if chunk.focus_key is not None and chunk.sequence is not None:
                self._buffer.append(KeyPress(chunk.focus_key, chunk.sequence))
            elif chunk.text:
                self.vt100_parser.feed(chunk.text)

    def _feed_text_with_terminal_events(self, data: str) -> None:
        for chunk in self._osc11_parser.feed(data):
            if chunk.osc11_response is not None:
                self._buffer.append(KeyPress(OSC11_RESPONSE_KEY, chunk.osc11_response))
            elif chunk.text:
                self._feed_text_with_focus_events(chunk.text)

    def read_keys(self) -> list[KeyPress]:
        """Read keys, handling Koda terminal events before prompt_toolkit parsing."""
        self._feed_text_with_terminal_events(self.stdin_reader.read())
        result = self._buffer
        self._buffer = []
        return result

    def flush_keys(self) -> list[KeyPress]:
        """Flush pending OSC 11 and prompt_toolkit input."""
        self._feed_text_with_focus_events(self._osc11_parser.flush())
        self.vt100_parser.feed(self._focus_parser.flush())
        return super().flush_keys()
