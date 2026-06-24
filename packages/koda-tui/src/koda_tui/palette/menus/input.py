from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.palette import Palette


_TITLE = "Input Mode"
_LIST_HEADING = "Set preferred input mode while assistant responds"

_INPUT_MODE_OPTIONS: tuple[tuple[bool, str, str], ...] = (
    (False, "Prefer steer", "Enter steers; Alt+Enter queues"),
    (True, "Prefer queue", "Enter queues; Alt+Enter steers"),
)


class InputMenu:
    """Input mode selection submenu."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._settings = palette.app_settings

    def items(self) -> list[ListItem]:
        """Build input mode selection items."""
        current = self._settings.tui.queue_inputs
        return [
            ListItem(
                id=f"select_input_mode:{'queue' if queue_inputs else 'steer'}",
                label=label,
                detail=detail,
                marker="*" if current == queue_inputs else None,
                marker_style="class:palette.current" if current == queue_inputs else None,
                data="queue" if queue_inputs else "steer",
            )
            for queue_inputs, label, detail in _INPUT_MODE_OPTIONS
        ]

    def open(self) -> None:
        """Open the input mode submenu."""
        self._palette.open_palette(self.items(), title=_TITLE, list_heading=_LIST_HEADING)

    def select(self, mode: str) -> None:
        """Handle input mode selection."""
        self._settings.tui.set("queue_inputs", mode == "queue")
        self._palette.close_all_overlays()
