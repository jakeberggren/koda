from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common import SettingsManager
    from koda_common.contracts import KodaBackend, ModelDefinition
    from koda_tui.ui.palette.palette_manager import PaletteManager


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
    settings.model = model.id
    palette_manager.close_all()


def get_commands(
    backend: KodaBackend,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the model selection palette."""
    provider = settings.provider
    models = backend.list_models(provider)

    return [
        Command(
            label=_format_model_label(model, settings),
            handler=partial(_select_model, model, settings, palette_manager),
            description="",
            group=settings.provider,
        )
        for model in models
    ]
