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
    catalog_service: KodaService,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    """Open dialog to enter API key for a provider."""
    palette_manager.open_dialog(
        provider=_display_name(provider),
        on_submit=partial(
            _submit_provider_api_key,
            provider,
            catalog_service,
            settings,
            palette_manager,
        ),
    )


def _auto_select_first_model(
    provider: ProviderDefinition,
    catalog_service: KodaService,
    settings: SettingsManager,
) -> bool:
    if settings.model is not None:
        return True

    provider_models = catalog_service.list_models(provider.id)
    if not provider_models:
        return True

    result = actions.select_model(
        current_model=None,
        model=provider_models[0],
        settings=settings,
    )
    if result.ok:
        return True

    log.warning(
        "cmd_auto_select_provider_model_failed",
        provider=provider.id,
        error=result.error,
    )
    return False


def _submit_provider_api_key(
    provider: ProviderDefinition,
    catalog_service: KodaService,
    settings: SettingsManager,
    palette_manager: PaletteManager,
    key: str,
) -> None:
    result = actions.set_provider_api_key(provider.id, key, settings)
    if not result.ok:
        log.warning("cmd_set_provider_api_key_failed", provider=provider.id, error=result.error)
        # TODO: surface action errors in the palette/status UI.
        return

    if not _auto_select_first_model(provider, catalog_service, settings):
        return

    palette_manager.close_all()


def get_commands(
    catalog_service: KodaService,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get commands for the provider selection palette."""
    providers = catalog_service.list_providers()

    return [
        Command(
            label=_format_provider_label(provider, settings),
            handler=partial(
                _open_api_key_dialog,
                provider,
                catalog_service,
                settings,
                palette_manager,
            ),
            description=f"Configure {_display_name(provider)} API key",
        )
        for provider in providers
    ]
