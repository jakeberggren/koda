"""Model palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import strings
from koda_tui.ui.widgets import ListItem, Picker

if TYPE_CHECKING:
    from koda.llm import Model
    from koda_tui.palette.context import PaletteContext


log = get_logger(__name__)

_LABEL_WIDTH = 32  # Longer model names are cut, so details line up.


class ModelMenu:
    """Model submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._catalog = context.catalog
        self._settings = context.settings

    def items(self) -> list[ListItem[Model]]:
        """Build model selection items."""
        provider_names = {p.id: p.name for p in self._catalog.providers()}
        return [
            self._item_for_model(model, provider_names.get(model.provider))
            for model in self._catalog.models()
            if model.is_connected(self._settings.core)
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
        try:
            self._settings.core.update(provider=model.provider, model=model.id)
        except ValueError:
            log.warning("select_model_failed", model_id=model.id)
            return
        self._overlays.close_all()

    def _item_for_model(self, model: Model, provider_name: str | None) -> ListItem[Model]:
        is_active = (
            self._settings.core.provider == model.provider and self._settings.core.model == model.id
        )
        return ListItem(
            label=model.name,
            detail=self._detail(model),
            group=provider_name,
            current=is_active,
            data=model,
        )

    def _detail(self, model: Model) -> str:
        """The connection ``model`` uses, when its provider has several connected."""
        credentials = self._settings.core
        provider = self._catalog.provider(model.provider)
        if sum(c.is_connected(credentials) for c in provider.connections) <= 1:
            return ""
        return model.connection(credentials).detail or model.detail or ""
