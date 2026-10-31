"""Palette context: what the palette's menus work with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda_tui.ui.widgets import Picker

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_tui.messaging import Conversation, Outbox
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState
    from koda_tui.terminal import Terminal
    from koda_tui.ui.overlays import Overlays
    from koda_tui.ui.primitives import ListItem


@dataclass(frozen=True, slots=True)
class PaletteContext:
    """Where menus open their pickers and dialogs, and the parts of Koda they act on."""

    overlays: Overlays
    service: KodaService
    settings: AppSettings
    state: AppState
    conversation: Conversation
    outbox: Outbox
    terminal: Terminal

    def choose[T](
        self,
        title: str,
        items: list[ListItem[T]],
        *,
        heading: str,
        on_choose: Callable[[T], None],
    ) -> None:
        """Open a picker over ``items``; choosing one passes its data to ``on_choose``
        and closes the palette."""

        def chosen(item: ListItem[T]) -> None:
            on_choose(item.data)
            self.overlays.close_all()

        self.overlays.open(
            Picker(title, items, on_select=chosen, heading=heading, on_close=self.overlays.close)
        )
