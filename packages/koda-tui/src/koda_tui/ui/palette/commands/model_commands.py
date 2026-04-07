from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.ui.palette.commands.command import Command
from koda_tui.utils.model_selection import find_model

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager
    from koda_service import CatalogService
    from koda_service.types import ModelDefinition, ProviderDefinition
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "bergetai": "BergetAI",
}


def _provider_display_name(provider: str) -> str:
    """Format provider key as a human-readable display label."""
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.title())


def _format_model_label(model: ModelDefinition, settings: SettingsManager) -> str:
    """Format model label with active status."""
    label = model.name
    if settings.model == model.id:
        label += " [active]"
    return label


def _select_model(
    model: ModelDefinition,
    catalog_service: CatalogService[ProviderDefinition, ModelDefinition],
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    """Select a model and close the palette."""
    current_models = catalog_service.list_selectable_models()
    current_model = find_model(
        current_models,
        provider=settings.provider,
        model_id=settings.model,
    )
    result = actions.select_model(current_model, model, settings)
    if not result.ok:
        log.warning("cmd_select_model_failed", model_id=model.id, provider=model.provider)
        # TODO: surface action errors in the palette/status UI.
        return
    palette_manager.close_all()


def get_commands(
    catalog_service: CatalogService[ProviderDefinition, ModelDefinition],
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the model selection palette."""
    models = catalog_service.list_selectable_models()

    return [
        Command(
            label=_format_model_label(model, settings),
            handler=partial(_select_model, model, catalog_service, settings, palette_manager),
            description="",
            group=_provider_display_name(model.provider),
        )
        for model in models
    ]
