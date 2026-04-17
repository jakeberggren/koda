from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service.types import ModelDefinition

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "bergetai": "BergetAI",
}


def _provider_display_name(provider: str) -> str:
    """Format provider key as a human-readable display label."""

    return PROVIDER_DISPLAY_NAMES.get(provider, provider.title())


def _format_model_label(model: ModelDefinition, active_model_id: str | None) -> str:
    """Format model label with active status."""

    label = model.name
    if active_model_id == model.id:
        label += " [active]"
    return label


def get_commands(
    models: list[ModelDefinition],
    active_model_id: str | None,
    on_select: Callable[[ModelDefinition], None],
) -> list[Command]:
    """Build commands for the model selection palette."""

    return [
        Command(
            label=_format_model_label(model, active_model_id),
            handler=partial(on_select, model),
            description="",
            group=_provider_display_name(model.provider),
        )
        for model in models
    ]
