"""Exit: a second Ctrl+C confirms leaving Koda."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_tui.state import AppState

EXIT_TIMEOUT = 3.0  # Seconds a second Ctrl+C has to come within to exit.


class ExitPrompt:
    """Asks for a second Ctrl+C before exiting, through ``state.exit_requested``,
    until ``EXIT_TIMEOUT`` runs out."""

    def __init__(self, state: AppState, *, invalidate: Callable[[], None]) -> None:
        self._state = state
        self._invalidate = invalidate
        self._dismissals = 0  # A timeout only dismisses the ask it was started for.

    def confirm(self) -> bool:
        """Whether this Ctrl+C confirms the exit; the first press only asks."""
        if self._state.exit_requested:
            self.dismiss()
            return True
        self._state.exit_requested = True
        dismissals = self._dismissals
        with suppress(RuntimeError):  # Without a running loop, it asks until dismissed.
            asyncio.get_running_loop().call_later(EXIT_TIMEOUT, self._expire, dismissals)
        self._invalidate()
        return False

    def dismiss(self) -> None:
        """Stop asking for a second Ctrl+C."""
        self._dismissals += 1
        if self._state.exit_requested:
            self._state.exit_requested = False
            self._invalidate()

    def _expire(self, dismissals: int) -> None:
        if dismissals == self._dismissals:
            self.dismiss()
