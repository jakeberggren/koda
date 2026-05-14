from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

_MAX_MODEL_LABEL_LENGTH = 24
_ELLIPSIS = "..."


if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service.types import ModelDefinition, ProviderDefinition


def _truncate_label(label: str, max_length: int) -> str:
    """Truncate long labels while preserving an ellipsis suffix."""

    if len(label) <= max_length:
        return label
    if max_length <= len(_ELLIPSIS):
        return _ELLIPSIS[:max_length]
    return label[: max_length - len(_ELLIPSIS)] + _ELLIPSIS


def _format_model_label(
    model: ModelDefinition,
    active_provider_id: str | None,
    active_model_id: str | None,
) -> str:
    """Format model label with active status."""

    suffix = (
        " [active]" if active_provider_id == model.provider and active_model_id == model.id else ""
    )
    max_name_length = max(_MAX_MODEL_LABEL_LENGTH - len(suffix), 0)
    label = _truncate_label(model.name, max_name_length)
    return label + suffix


def get_commands(
    models: list[ModelDefinition],
    providers: list[ProviderDefinition],
    active_provider_id: str | None,
    active_model_id: str | None,
    on_select: Callable[[ModelDefinition], None],
) -> list[Command]:
    """Build commands for the model selection palette."""

    provider_names = {provider.id: provider.name for provider in providers}

    return [
        Command(
            label=_format_model_label(model, active_provider_id, active_model_id),
            handler=partial(on_select, model),
            description=model.description or "",
            group=provider_names[model.provider],
        )
        for model in models
    ]
