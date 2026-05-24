"""Thinking-level palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.palette.items import ListItem
from koda_tui.utils.model_selection import find_model, supported_thinking_options

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.palette.palette import Palette


log = get_logger(__name__)

_TITLE = "Set Thinking Level"
_LIST_HEADING = "Select Model Reasoning Effort"


class ThinkingMenu:
    """Thinking submenu behavior."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._service = palette.service
        self._settings = palette.app_settings

    def items(self) -> list[ListItem]:
        """Build thinking level selection items."""
        active_model = find_model(
            self._service.list_models(self._settings.core.provider),
            provider=self._settings.core.provider,
            model_id=self._settings.core.model,
        )
        options = supported_thinking_options(active_model)

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
        result = actions.set_thinking(thinking, self._settings.core)
        if not result.ok:
            log.warning("set_thinking_failed", thinking=thinking, error=result.error)
            return
        self._palette.close_all_overlays()
