"""Model selection commands."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common import SettingsManager
    from koda_tui.ui.palette.palette_manager import PaletteManager

MODELS_BY_PROVIDER: dict[str, list[str]] = {
    "openai": [
        "gpt-5.2-codex",
        "gpt-5.2",
        "gpt-5.1-codex",
        "gpt-5.1",
        "gpt-5-mini",
        "gpt-5-nano",
    ],
    "anthropic": [
        "claude-opus-4.5",
        "claude-sonnet-4",
        "claude-haiku-3.5",
    ],
}


def _format_model_label(model: str, settings: SettingsManager) -> str:
    """Format model label with active status."""
    label = model
    if settings.model == model:
        label += " [active]"
    return label


def _select_model(
    model: str,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    """Select a model and close the palette."""
    settings.model = model
    palette_manager.close_all()


def get_commands(
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the model selection palette."""
    provider = settings.provider
    models = MODELS_BY_PROVIDER.get(provider, [])

    return [
        Command(
            label=_format_model_label(model, settings),
            handler=partial(_select_model, model, settings, palette_manager),
            description="",
        )
        for model in models
    ]
