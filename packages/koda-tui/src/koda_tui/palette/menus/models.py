"""Model palette items and actions."""

from __future__ import annotations

from copy import replace
from typing import TYPE_CHECKING

from koda_tui import strings
from koda_tui.ui.widgets import ListItem, Picker

if TYPE_CHECKING:
    from koda.llm import Model
    from koda_tui.palette.context import PaletteContext


_LABEL_WIDTH = 32  # Longer model names are cut, so details line up.


class ModelMenu:
    """Model submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._catalog = context.catalog
        self._context = context

    def items(self) -> list[ListItem[Model]]:
        """Build model selection items."""
        provider_names = {p.id: p.name for p in self._catalog.providers()}
        return [
            self._item_for_model(model, provider_names.get(model.provider))
            for model in self._context.catalog.connected.models
        ]

    def open(self) -> None:
        """Open the model selection submenu."""
        self._overlays.open(
            Picker(
                strings.Palette.Models.TITLE,
                self.items(),
                on_select=lambda item: self.select(item.data),
                label_width=_LABEL_WIDTH,
                on_close=self._overlays.close,
            ),
        )

    def select(self, model: Model) -> None:
        """Handle model selection."""
        settings = self._context.settings
        agent_settings = replace(settings.agent_settings, provider=model.provider, model=model.id)
        self._context.update_settings(replace(settings, agent_settings=agent_settings))
        self._overlays.close_all()

    def _item_for_model(self, model: Model, provider_name: str | None) -> ListItem[Model]:
        return ListItem(
            label=model.name,
            detail=self._detail(model),
            group=provider_name,
            current=model == self._context.state.active_model,
            data=model,
        )

    def _detail(self, model: Model) -> str:
        """The connection ``model`` uses, when its provider has several connected."""
        connected = self._context.catalog.connected
        if len(connected.connections(self._catalog.provider(model.provider))) <= 1:
            return ""
        return connected.connection(model).detail
