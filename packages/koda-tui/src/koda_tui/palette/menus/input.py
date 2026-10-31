"""Input mode palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.ui.primitives import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.context import PaletteContext


_TITLE = "Input Mode"
_LIST_HEADING = "Set preferred input mode while assistant responds"

# Whether Enter queues, how it is listed, and what it means for both keys.
_INPUT_MODE_OPTIONS: tuple[tuple[bool, str, str], ...] = (
    (False, "Prefer steer", "Enter steers; Alt+Enter queues"),
    (True, "Prefer queue", "Enter queues; Alt+Enter steers"),
)


class InputMenu:
    """Picks what Enter does while Koda responds: queue the message, or steer with it."""

    def __init__(self, context: PaletteContext) -> None:
        self._context = context

    def open(self) -> None:
        current = self._context.settings.tui.queue_inputs
        items = [
            ListItem(label=label, detail=detail, current=current == queue, data=queue)
            for queue, label, detail in _INPUT_MODE_OPTIONS
        ]
        self._context.choose(_TITLE, items, heading=_LIST_HEADING, on_choose=self._select)

    def _select(self, queue: bool) -> None:  # noqa: FBT001 - the picked item's data
        self._context.settings.tui.set("queue_inputs", queue)
