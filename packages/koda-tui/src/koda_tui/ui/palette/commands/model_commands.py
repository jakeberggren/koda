from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service.types import ModelDefinition, ProviderDefinition


def _format_model_label(model: ModelDefinition, active_model_id: str | None) -> str:
    """Format model label with active status."""

    label = model.name
    if active_model_id == model.id:
        label += " [active]"
    return label


def get_commands(
    models: list[ModelDefinition],
    providers: list[ProviderDefinition],
    active_model_id: str | None,
    on_select: Callable[[ModelDefinition], None],
) -> list[Command]:
    """Build commands for the model selection palette."""

    provider_names = {provider.id: provider.name for provider in providers}

    return [
        Command(
            label=_format_model_label(model, active_model_id),
            handler=partial(on_select, model),
            description="",
            group=provider_names[model.provider],
        )
        for model in models
    ]
