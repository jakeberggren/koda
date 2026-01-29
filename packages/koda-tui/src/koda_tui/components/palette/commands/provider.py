"""Provider connection commands."""

from __future__ import annotations

import shutil
from functools import partial
from typing import TYPE_CHECKING

from koda_tui.components.dialogs import ApiKeyDialog
from koda_tui.components.palette.commands.base import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_common import SettingsManager
    from koda_tui.clients import Client
    from koda_tui.components.palette.manager import PaletteManager


def _format_provider_label(provider: str, settings: SettingsManager) -> str:
    """Format provider label with connected status."""
    label = provider.title()
    if settings.get_api_key(provider):
        label += " [connected]"
    return label


def _open_api_key_dialog(
    provider: str,
    settings: SettingsManager,
    palette_manager: PaletteManager,
    on_close: Callable[[], None],
) -> None:
    """Open dialog to enter API key for a provider."""

    def on_submit(key: str) -> None:
        settings.set_api_key(provider, key)
        palette_manager.clear()  # Close everything on successful save

    dialog = ApiKeyDialog(
        provider=provider.title(),
        on_submit=on_submit,
        on_cancel=on_close,
    )

    # Calculate dialog width
    term_width = shutil.get_terminal_size().columns
    dialog_width = max(40, min(60, term_width // 2))

    palette_manager.push(dialog, width=dialog_width)


def get_provider_commands(
    client: Client,
    settings: SettingsManager,
    palette_manager: PaletteManager,
    on_close: Callable[[], None],
) -> list[Command]:
    """Get commands for the provider selection palette.

    Args:
        settings: Settings manager for API key access
        palette_manager: Palette manager for pushing dialogs
        on_close: Callback when dialog is closed/cancelled
    """
    providers = client.list_providers()

    return [
        Command(
            label=_format_provider_label(provider, settings),
            handler=partial(_open_api_key_dialog, provider, settings, palette_manager, on_close),
            description=f"Configure {provider} API key",
        )
        for provider in providers
    ]
