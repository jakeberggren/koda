from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common import SettingsManager
    from koda_common.contracts import KodaBackend
    from koda_tui.ui.palette.palette_manager import PaletteManager

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "bergetai": "BergetAI",
}


def _display_name(provider: str) -> str:
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.title())


def _format_provider_label(provider: str, settings: SettingsManager) -> str:
    """Format provider label with connected status."""
    label = _display_name(provider)
    if settings.get_api_key(provider):
        label += " [connected]"
    return label


def _open_api_key_dialog(
    provider: str,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    """Open dialog to enter API key for a provider."""

    def on_submit(key: str) -> None:
        settings.set_api_key(provider, key)
        palette_manager.close_all()

    palette_manager.open_dialog(
        provider=_display_name(provider),
        on_submit=on_submit,
    )


def get_commands(
    backend: KodaBackend,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the provider selection palette."""
    providers = backend.list_providers()

    return [
        Command(
            label=_format_provider_label(provider, settings),
            handler=partial(_open_api_key_dialog, provider, settings, palette_manager),
            description=f"Configure {_display_name(provider)} API key",
        )
        for provider in providers
    ]
