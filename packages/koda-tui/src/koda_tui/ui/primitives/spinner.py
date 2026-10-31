"""Spinner primitive: an animated one-cell activity indicator."""

from __future__ import annotations

import asyncio
import time

from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout import FormattedTextControl, Window

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
FRAMES_PER_SECOND = 10


class Spinner:
    """A spinning frame, advanced by the clock. While it is drawn, it asks for the next
    frame to be drawn too; once it isn't, it stops asking."""

    def __init__(self, *, style: str = "") -> None:
        self._next_frame: asyncio.TimerHandle | None = None
        self._window = Window(
            FormattedTextControl(lambda: [(style, self._frame())]),
            width=1,
            height=1,
            dont_extend_width=True,
        )

    def __pt_container__(self) -> Window:
        return self._window

    def _frame(self) -> str:
        self._ask_for_next_frame()
        return frame()

    def _ask_for_next_frame(self) -> None:
        if self._next_frame is not None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # Drawn outside a running app; nothing to animate.
        self._next_frame = loop.call_later(1 / FRAMES_PER_SECOND, self._redraw)

    def _redraw(self) -> None:
        self._next_frame = None
        get_app().invalidate()


def frame() -> str:
    """The spinner frame for the current moment."""
    return FRAMES[int(time.time() * FRAMES_PER_SECOND) % len(FRAMES)]
