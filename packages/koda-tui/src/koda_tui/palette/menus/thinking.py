"""Thinking-level palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.palette.palette import Palette


_TITLE = "Set Thinking Level"
_LIST_HEADING = "Select Model Reasoning Effort"


class ThinkingMenu:
    """Thinking submenu behavior."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._settings = palette.app_settings
        self._state = palette.state

    def items(self) -> list[ListItem]:
        """Build thinking level selection items."""
        if self._state.active_model is None:
            return []
        options = self._state.active_model.effective_thinking_options

        return [
            ListItem(
                id=f"select_thinking:{option.id}",
                label=option.label,
                description=option.description or "",
                marker="*" if self._settings.core.thinking == option.id else None,
                marker_style=(
                    "class:palette.current" if self._settings.core.thinking == option.id else None
                ),
                data=option.id,
            )
            for option in options
        ]

    def open(self) -> None:
        """Open the thinking selection submenu."""
        self._palette.open_palette(self.items(), title=_TITLE, list_heading=_LIST_HEADING)

    def select(self, thinking: ThinkingOptionId) -> None:
        """Handle thinking level selection."""
        self._settings.core.set("thinking", thinking)
        self._palette.close_all_overlays()
