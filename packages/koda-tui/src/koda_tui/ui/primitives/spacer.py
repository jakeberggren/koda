"""Spacer primitive: blank rows between sections."""

from __future__ import annotations

from prompt_toolkit.layout import Window

from koda_tui.appearance import Spacing


class Spacer:
    """Blank rows, ``Spacing.GAP`` high unless told otherwise."""

    def __init__(self, height: int = Spacing.GAP) -> None:
        self._window = Window(height=height)

    def __pt_container__(self) -> Window:
        return self._window
