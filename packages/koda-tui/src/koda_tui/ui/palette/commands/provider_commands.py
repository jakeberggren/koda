from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service.types import ProviderDefinition


def _display_name(provider: ProviderDefinition) -> str:
    """Return the user-facing provider name."""

    return provider.name


def _format_provider_label(provider: ProviderDefinition, connected_provider_ids: set[str]) -> str:
    """Format provider label with connected status."""

    label = _display_name(provider)
    if provider.id in connected_provider_ids:
        label += " [connected]"
    return label


def get_commands(
    providers: list[ProviderDefinition],
    connected_provider_ids: set[str],
    on_select: Callable[[ProviderDefinition], None],
) -> list[Command]:
    """Build commands for the provider selection palette."""

    return [
        Command(
            label=_format_provider_label(provider, connected_provider_ids),
            handler=partial(on_select, provider),
            description=f"Configure {_display_name(provider)} API key",
        )
        for provider in providers
    ]
