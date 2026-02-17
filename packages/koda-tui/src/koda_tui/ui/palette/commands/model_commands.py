from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common.contracts import KodaBackend, ModelDefinition
    from koda_common.settings import SettingsManager
    from koda_tui.ui.palette.palette_manager import PaletteManager

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
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    """Select a model and close the palette."""
    settings.provider = model.provider
    settings.model = model.id
    palette_manager.close_all()


def get_commands(
    backend: KodaBackend,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the model selection palette."""
    models = backend.list_models()

    return [
        Command(
            label=_format_model_label(model, settings),
            handler=partial(_select_model, model, settings, palette_manager),
            description="",
            group=_provider_display_name(model.provider),
        )
        for model in models
    ]
