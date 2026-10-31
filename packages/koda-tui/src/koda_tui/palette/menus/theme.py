"""Theme palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.appearance import AUTO_THEME, THEMES
from koda_tui.overlays.list.renderer import CURRENT_STYLE
from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.palette import Palette


_TITLE = "Select Theme"
_LIST_HEADING = "Select UI Theme"

_AUTO_OPTION = (AUTO_THEME, "Auto", "Follow terminal theme when detectable")


def _theme_options() -> list[tuple[str, str, str]]:
    return [
        _AUTO_OPTION,
        *(
            (theme.name, theme.label, "Dark" if theme.dark else "Light")
            for theme in THEMES.values()
        ),
    ]


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
                id=f"select_theme:{theme}",
                label=label,
                detail=detail,
                marker="*" if current == theme else None,
                marker_style=CURRENT_STYLE if current == theme else None,
                data=theme,
            )
            for theme, label, detail in _theme_options()
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
