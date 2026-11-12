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
            for model in self._catalog.models()
            if model.is_connected(self._context.credentials)
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
        self._context.update_settings(
            replace(self._context.settings, provider=model.provider, model=model.id)
        )
        self._overlays.close_all()

    def _item_for_model(self, model: Model, provider_name: str | None) -> ListItem[Model]:
        settings = self._context.settings
        is_active = settings.provider == model.provider and settings.model == model.id
        return ListItem(
            label=model.name,
            detail=self._detail(model),
            group=provider_name,
            current=is_active,
            data=model,
        )

    def _detail(self, model: Model) -> str:
        """The connection ``model`` uses, when its provider has several connected."""
        credentials = self._context.credentials
        provider = self._catalog.provider(model.provider)
        if sum(c.is_connected(credentials) for c in provider.connections) <= 1:
            return ""
        return model.connection(credentials).detail or model.detail or ""
