from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager
    from koda_service import KodaService
    from koda_service.types import ProviderDefinition
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)


def _display_name(provider: ProviderDefinition) -> str:
    return provider.name


def _format_provider_label(provider: ProviderDefinition, settings: SettingsManager) -> str:
    """Format provider label with connected status."""
    label = _display_name(provider)
    if settings.get_api_key(provider.id):
        label += " [connected]"
    return label


def _open_api_key_dialog(
    provider: ProviderDefinition,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    """Open dialog to enter API key for a provider."""

    def on_submit(key: str) -> None:
        result = actions.set_provider_api_key(provider.id, key, settings)
        if not result.ok:
            log.warning("cmd_set_provider_api_key_failed", provider=provider.id, error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    palette_manager.open_dialog(
        provider=_display_name(provider),
        on_submit=on_submit,
    )


def get_commands(
    service: KodaService,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the provider selection palette."""
    providers = service.list_providers()

    return [
        Command(
            label=_format_provider_label(provider, settings),
            handler=partial(_open_api_key_dialog, provider, settings, palette_manager),
            description=f"Configure {_display_name(provider)} API key",
        )
        for provider in providers
    ]
