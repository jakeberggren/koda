"""Model palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui.appearance import Tokens
from koda_tui.ui.primitives import ListItem
from koda_tui.ui.widgets import Picker

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.llm import ModelDefinition
    from koda_tui.palette.context import PaletteContext


log = get_logger(__name__)

_TITLE = "Switch Model"
_LABEL_WIDTH = 32  # Longer model names are cut, so details line up.
_PROXY_MANAGED_MODEL_FOOTER: StyleAndTextTuples = [
    (
        Tokens.Text.WARNING,
        "Proxy-managed credentials: model access is verified on request.",
    )
]


class ModelMenu:
    """Model submenu behavior."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._service = context.service
        self._settings = context.settings

    def items(self) -> list[ListItem[ModelDefinition]]:
        """Build model selection items and footer."""
        provider_names = {p.id: p.name for p in self._service.list_providers()}

        return [
            self._item_for_model(model, provider_names.get(model.provider))
            for model in self._service.list_configured_models()
        ]

    def open(self) -> None:
        """Open the model selection submenu."""
        footer = _PROXY_MANAGED_MODEL_FOOTER if self._settings.proxy_managed else None
        self._overlays.open(
            Picker(
                _TITLE,
                self.items(),
                on_select=lambda item: self.select(item.data),
                footer=footer,
                label_width=_LABEL_WIDTH,
                on_close=self._overlays.close,
            ),
        )

    def select(self, model: ModelDefinition) -> None:
        """Handle model selection."""
        try:
            self._settings.core.update(provider=model.provider, model=model.id)
        except ValueError:
            log.warning("select_model_failed", model_id=model.id)
            return
        self._overlays.close_all()

    def _item_for_model(
        self, model: ModelDefinition, provider_name: str | None
    ) -> ListItem[ModelDefinition]:
        is_active = (
            self._settings.core.provider == model.provider and self._settings.core.model == model.id
        )
        return ListItem(
            label=model.name,
            detail=model.detail or "",
            group=provider_name,
            current=is_active,
            data=model,
        )
