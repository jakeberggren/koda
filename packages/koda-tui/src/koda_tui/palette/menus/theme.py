"""Theme palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.appearance import THEMES
from koda_tui.ui.primitives import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.context import PaletteContext


_TITLE = "Select Theme"
_LIST_HEADING = "Select UI Theme"


class ThemeMenu:
    """Picks the UI theme. Picking the current one asks the terminal for its
    background again, as for a terminal that changed between light and dark."""

    def __init__(self, context: PaletteContext) -> None:
        self._context = context

    def open(self) -> None:
        current = self._context.settings.tui.theme
        items = [
            ListItem(
                label=theme.label,
                detail=theme.description,
                current=current == theme.name,
                data=theme.name,
            )
            for theme in THEMES.values()
        ]
        self._context.choose(_TITLE, items, heading=_LIST_HEADING, on_choose=self._select)

    def _select(self, theme: str) -> None:
        if self._context.settings.tui.theme == theme:
            self._context.terminal.ask_background()
        else:
            self._context.settings.tui.set("theme", theme)
