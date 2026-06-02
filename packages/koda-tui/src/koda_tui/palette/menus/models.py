"""Model palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.llm import ModelDefinition, ThinkingOptionId
    from koda_common.settings import SettingsManager
    from koda_tui.palette.palette import Palette


log = get_logger(__name__)

_TITLE = "Switch Model"
_PROXY_MANAGED_MODEL_FOOTER: StyleAndTextTuples = [
    (
        "fg:ansiyellow",
        "Proxy-managed credentials: model access is verified on request.",
    )
]


def _truncate_label(label: str, max_length: int) -> str:
    if len(label) <= max_length:
        return label
    ellipsis = "..."
    if max_length <= len(ellipsis):
        return ellipsis[:max_length]
    return label[: max_length - len(ellipsis)] + ellipsis


def _normalize_thinking_for_model_switch(
    current: ThinkingOptionId,
    *,
    current_model: ModelDefinition | None,
    new_model: ModelDefinition,
) -> ThinkingOptionId:
    new_ids = [option.id for option in new_model.effective_thinking_options]
    if current in new_ids:
        return current

    current_options = (
        current_model.effective_thinking_options
        if current_model is not None
        else new_model.effective_thinking_options
    )
    current_ids = [option.id for option in current_options]
    try:
        current_index = current_ids.index(current)
    except ValueError:
        return new_ids[0]

    return new_ids[min(current_index, len(new_ids) - 1)]


def apply_model_selection(
    model: ModelDefinition,
    *,
    current_model: ModelDefinition | None,
    settings: SettingsManager,
) -> None:
    changes: dict[str, object] = {
        "provider": model.provider,
        "model": model.id,
    }
    normalized_thinking = _normalize_thinking_for_model_switch(
        settings.thinking,
        current_model=current_model,
        new_model=model,
    )
    if normalized_thinking != settings.thinking:
        changes["thinking"] = normalized_thinking
    settings.update(**changes)


class ModelMenu:
    """Model submenu behavior."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._service = palette.service
        self._settings = palette.app_settings

    def _is_proxy_managed(self) -> bool:
        return self._settings.core.credential_mode == "proxy-managed"

    def items(self) -> list[ListItem]:
        """Build model selection items and footer."""
        provider_names = {p.id: p.name for p in self._service.list_providers()}

        return [
            self._item_for_model(model, provider_names.get(model.provider))
            for model in self._service.list_configured_models()
        ]

    def open(self) -> None:
        """Open the model selection submenu."""
        proxy_managed = self._is_proxy_managed()
        footer = _PROXY_MANAGED_MODEL_FOOTER if proxy_managed else None
        self._palette.open_palette(self.items(), title=_TITLE, footer=footer)

    def select(self, model: ModelDefinition) -> None:
        """Handle model selection."""
        try:
            apply_model_selection(
                model,
                current_model=self._palette.state.active_model,
                settings=self._settings.core,
            )
        except ValueError:
            log.warning("select_model_failed", model_id=model.id)
            return
        self._palette.close_all_overlays()

    def _item_for_model(self, model: ModelDefinition, provider_name: str | None) -> ListItem:
        is_active = (
            self._settings.core.provider == model.provider and self._settings.core.model == model.id
        )
        return ListItem(
            id=f"select_model:{model.id}",
            label=_truncate_label(model.name, 24),
            detail=model.detail or "",
            group=provider_name,
            marker="*" if is_active else None,
            marker_style="class:palette.current" if is_active else None,
            data=model,
        )
