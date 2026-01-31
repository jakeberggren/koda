from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prompt_toolkit.output import Output

# DEC private mode 2026 — Synchronized Output.
# The terminal buffers all output between begin/end markers
# and displays it as a single atomic frame, eliminating tearing.
# Terminals that don't support it simply ignore the sequences.
_SYNC_BEGIN = "\033[?2026h"
_SYNC_END = "\033[?2026l"


class SynchronizedOutput:
    """Output proxy that wraps each render frame in DEC mode 2026 sequences."""

    def __init__(self, output: Output) -> None:
        self._output = output
        self._in_frame = False

    def write(self, data: str) -> None:
        if not self._in_frame:
            self._output.write_raw(_SYNC_BEGIN)
            self._in_frame = True
        self._output.write(data)

    def write_raw(self, data: str) -> None:
        if not self._in_frame:
            self._output.write_raw(_SYNC_BEGIN)
            self._in_frame = True
        self._output.write_raw(data)

    def flush(self) -> None:
        if self._in_frame:
            self._output.write_raw(_SYNC_END)
            self._in_frame = False
        self._output.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._output, name)
