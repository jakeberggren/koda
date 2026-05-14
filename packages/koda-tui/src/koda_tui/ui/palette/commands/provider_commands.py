from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command, CommandStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service.types import ProviderDefinition


def get_commands(
    providers: list[ProviderDefinition],
    connected_provider_ids: set[str],
    on_select: Callable[[ProviderDefinition], None],
) -> list[Command]:
    """Build commands for the provider selection palette."""

    return [
        Command(
            label=provider.name,
            handler=partial(on_select, provider),
            description=provider.description or "",
            status=CommandStatus.CONNECTED if provider.id in connected_provider_ids else None,
        )
        for provider in providers
    ]
