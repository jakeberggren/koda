from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command, CommandMarker

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.llm import ProviderDefinition

PROXY_MANAGED_PROVIDER_FOOTER: StyleAndTextTuples = [
    (
        "fg:ansiyellow",
        "Proxy-managed credentials: use sbx secret set outside Koda; "
        "connectivity is verified on request.",
    )
]


def get_commands(
    providers: list[ProviderDefinition],
    connected_provider_ids: set[str],
    on_select: Callable[[ProviderDefinition], None],
    *,
    proxy_managed: bool = False,
) -> list[Command]:
    """Build commands for the provider selection palette."""

    return [
        Command(
            label=provider.name,
            handler=partial(on_select, provider),
            description=provider.description or "",
            marker=CommandMarker(marker="✓")
            if provider.id in connected_provider_ids and not proxy_managed
            else None,
        )
        for provider in providers
    ]
