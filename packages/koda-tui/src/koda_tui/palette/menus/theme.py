"""Theme palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from koda_tui.palette.palette import Palette
    from koda_tui.theme import ThemeSetting


_TITLE = "Select Theme"
_LIST_HEADING = "Select UI Theme"

_THEME_OPTIONS: tuple[tuple[ThemeSetting, str, str], ...] = (
    ("auto", "Auto", "Follow terminal theme when detectable"),
    ("light", "Light", "Use light UI colors"),
    ("dark", "Dark", "Use dark UI colors"),
)


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
                marker_style="class:palette.current" if current == theme else None,
                data=theme,
            )
            for theme, label, detail in _THEME_OPTIONS
        ]

    def open(self) -> None:
        """Open the theme selection submenu."""
        self._palette.open_palette(self.items(), title=_TITLE, list_heading=_LIST_HEADING)

    def select(self, theme: ThemeSetting) -> None:
        """Handle theme selection."""
        if self._settings.tui.theme == theme:
            self._palette.refresh_theme(detect_terminal=theme == "auto")
        else:
            self._settings.tui.set("theme", theme)
        self._palette.close_all_overlays()
