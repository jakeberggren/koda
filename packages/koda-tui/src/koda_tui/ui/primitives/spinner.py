"""Spinner primitive: an animated one-cell activity indicator."""

from __future__ import annotations

import time

from prompt_toolkit.layout import FormattedTextControl, Window

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
FRAMES_PER_SECOND = 10


class Spinner:
    """A spinning frame, advanced by the clock each time the screen is drawn."""

    def __init__(self, *, style: str = "") -> None:
        self._window = Window(
            FormattedTextControl(lambda: [(style, frame())]),
            width=1,
            height=1,
            dont_extend_width=True,
        )

    def __pt_container__(self) -> Window:
        return self._window


def frame() -> str:
    """The spinner frame for the current moment."""
    return FRAMES[int(time.time() * FRAMES_PER_SECOND) % len(FRAMES)]
