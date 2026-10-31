from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.ui.primitives import ListItem
from koda_tui.ui.widgets import Picker

if TYPE_CHECKING:
    from koda_tui.palette.context import PaletteContext


_TITLE = "Input Mode"
_LIST_HEADING = "Set preferred input mode while assistant responds"

_INPUT_MODE_OPTIONS: tuple[tuple[bool, str, str], ...] = (
    (False, "Prefer steer", "Enter steers; Alt+Enter queues"),
    (True, "Prefer queue", "Enter queues; Alt+Enter steers"),
)


class InputMenu:
    """Input mode selection submenu."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._settings = context.settings

    def items(self) -> list[ListItem[str]]:
        """Build input mode selection items."""
        current = self._settings.tui.queue_inputs
        return [
            ListItem(
                label=label,
                detail=detail,
                current=current == queue_inputs,
                data="queue" if queue_inputs else "steer",
            )
            for queue_inputs, label, detail in _INPUT_MODE_OPTIONS
        ]

    def open(self) -> None:
        """Open the input mode submenu."""
        self._overlays.open(
            Picker(
                _TITLE,
                self.items(),
                on_select=lambda item: self.select(item.data),
                heading=_LIST_HEADING,
                on_close=self._overlays.close,
            ),
        )

    def select(self, mode: str) -> None:
        """Handle input mode selection."""
        self._settings.tui.set("queue_inputs", mode == "queue")
        self._overlays.close_all()
