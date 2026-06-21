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
_FOCUS_REPORTING_ENABLE = "\033[?1004h"
_FOCUS_REPORTING_DISABLE = "\033[?1004l"


class SynchronizedOutput:
    """Output proxy that wraps each render frame in DEC mode 2026 sequences."""

    def __init__(self, output: Output) -> None:
        self._output = output
        self._in_frame = False
        self._focus_reporting = False

    def enable_focus_reporting(self) -> None:
        """Request xterm focus-in/focus-out events from supporting terminals."""
        if self._focus_reporting:
            return
        if self._in_frame:
            self.flush()
        self._output.write_raw(_FOCUS_REPORTING_ENABLE)
        self._output.flush()
        self._focus_reporting = True

    def disable_focus_reporting(self) -> None:
        """Disable xterm focus-in/focus-out events if they were enabled."""
        if not self._focus_reporting:
            return
        if self._in_frame:
            self.flush()
        self._output.write_raw(_FOCUS_REPORTING_DISABLE)
        self._output.flush()
        self._focus_reporting = False

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
