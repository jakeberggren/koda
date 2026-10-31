"""Theme palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.appearance import THEMES
from koda_tui.ui.primitives import ListItem
from koda_tui.ui.widgets import Picker

if TYPE_CHECKING:
    from koda_tui.palette.context import PaletteContext


_TITLE = "Select Theme"
_LIST_HEADING = "Select UI Theme"


class ThemeMenu:
    """Theme selection submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._terminal = context.terminal
        self._settings = context.settings

    def items(self) -> list[ListItem[str]]:
        """Build theme selection items."""
        current = self._settings.tui.theme
        return [
            ListItem(
                label=theme.label,
                detail=theme.description,
                current=current == theme.name,
                data=theme.name,
            )
            for theme in THEMES.values()
        ]

    def open(self) -> None:
        """Open the theme selection submenu."""
        self._overlays.open(
            Picker(
                _TITLE,
                self.items(),
                on_select=lambda item: self.select(item.data),
                heading=_LIST_HEADING,
                on_close=self._overlays.close,
            ),
        )

    def select(self, theme: str) -> None:
        """Handle theme selection."""
        if self._settings.tui.theme == theme:
            self._terminal.ask_background()
        else:
            self._settings.tui.set("theme", theme)
        self._overlays.close_all()
