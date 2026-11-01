"""Input mode palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui import strings
from koda_tui.ui.widgets import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.context import PaletteContext


# Whether Enter queues, how it is listed, and what it means for both keys.
_INPUT_MODE_OPTIONS: tuple[tuple[bool, str, str], ...] = (
    (False, strings.Palette.InputMode.STEER, strings.Palette.InputMode.STEER_DETAIL),
    (True, strings.Palette.InputMode.QUEUE, strings.Palette.InputMode.QUEUE_DETAIL),
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
        self._context.choose(
            strings.Palette.InputMode.TITLE,
            items,
            heading=strings.Palette.InputMode.HEADING,
            on_choose=self._select,
        )

    def _select(self, queue: bool) -> None:  # noqa: FBT001 - the picked item's data
        self._context.settings.tui.set("queue_inputs", queue)
