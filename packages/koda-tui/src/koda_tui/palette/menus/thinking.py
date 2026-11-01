"""Thinking-level palette items and actions."""

from __future__ import annotations

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
        current = self._context.settings.core.thinking
        items: list[ListItem[ThinkingOptionId]] = [
            ListItem(
                label=option.label,
                detail=option.description or "",
                current=current == option.id,
                data=option.id,
            )
            for option in (model.effective_thinking_options if model else [])
        ]
        self._context.choose(
            strings.Palette.Thinking.TITLE,
            items,
            heading=strings.Palette.Thinking.HEADING,
            on_choose=self._select,
        )

    def _select(self, thinking: ThinkingOptionId) -> None:
        self._context.settings.core.set("thinking", thinking)
