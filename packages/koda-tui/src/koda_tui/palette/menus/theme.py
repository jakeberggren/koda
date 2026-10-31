"""Theme palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.appearance import THEMES
from koda_tui.ui.primitives import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.palette import Palette


_TITLE = "Select Theme"
_LIST_HEADING = "Select UI Theme"


class ThemeMenu:
    """Theme selection submenu behavior."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._settings = palette.app_settings

    def items(self) -> list[ListItem]:
        """Build theme selection items."""
        current = self._settings.tui.theme
        return [
            ListItem(
                id=f"select_theme:{theme.name}",
                label=theme.label,
                detail=theme.description,
                current=current == theme.name,
                data=theme.name,
            )
            for theme in THEMES.values()
        ]

    def open(self) -> None:
        """Open the theme selection submenu."""
        self._palette.open_palette(self.items(), title=_TITLE, list_heading=_LIST_HEADING)

    def select(self, theme: str) -> None:
        """Handle theme selection."""
        if self._settings.tui.theme == theme:
            self._palette.refresh_theme()
        else:
            self._settings.tui.set("theme", theme)
        self._palette.close_all_overlays()
