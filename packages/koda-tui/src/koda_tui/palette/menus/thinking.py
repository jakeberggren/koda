"""Thinking-level palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.ui.primitives import ListItem
from koda_tui.ui.widgets import Picker

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.palette.context import PaletteContext


_TITLE = "Set Thinking Level"
_LIST_HEADING = "Select Model Reasoning Effort"


class ThinkingMenu:
    """Thinking submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._settings = context.settings
        self._state = context.state

    def items(self) -> list[ListItem[ThinkingOptionId]]:
        """Build thinking level selection items."""
        if self._state.active_model is None:
            return []
        options = self._state.active_model.effective_thinking_options

        return [
            ListItem(
                label=option.label,
                detail=option.description or "",
                current=self._settings.core.thinking == option.id,
                data=option.id,
            )
            for option in options
        ]

    def open(self) -> None:
        """Open the thinking selection submenu."""
        self._overlays.open(
            Picker(
                _TITLE,
                self.items(),
                on_select=lambda item: self.select(item.data),
                heading=_LIST_HEADING,
                on_close=self._overlays.close,
            ),
        )

    def select(self, thinking: ThinkingOptionId) -> None:
        """Handle thinking level selection."""
        self._settings.core.set("thinking", thinking)
        self._overlays.close_all()
