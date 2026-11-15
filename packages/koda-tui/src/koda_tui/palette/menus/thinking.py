"""Thinking-level palette items and actions."""

from __future__ import annotations

from copy import replace
from typing import TYPE_CHECKING

from koda_tui import strings
from koda_tui.ui.widgets import ListItem

if TYPE_CHECKING:
    from koda.llm import ThinkingOptionId
    from koda_tui.palette.context import PaletteContext


class ThinkingMenu:
    """Picks the active model's thinking level."""

    def __init__(self, context: PaletteContext) -> None:
        self._context = context

    def open(self) -> None:
        model = self._context.state.active_model
        current = self._context.settings.agent_settings.thinking
        items: list[ListItem[ThinkingOptionId]] = [
            ListItem(
                label=option.label,
                detail=option.description or "",
                current=current == option.id,
                data=option.id,
            )
            for option in (model.thinking.options if model else ())
        ]
        self._context.choose(
            strings.Palette.Thinking.TITLE,
            items,
            heading=strings.Palette.Thinking.HEADING,
            on_choose=self._select,
        )

    def _select(self, thinking: ThinkingOptionId) -> None:
        settings = self._context.settings
        agent_settings = replace(settings.agent_settings, thinking=thinking)
        self._context.update_settings(replace(settings, agent_settings=agent_settings))
