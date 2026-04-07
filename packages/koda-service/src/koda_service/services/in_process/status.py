from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.llm.exceptions import ApiKeyNotConfiguredError, EmptyApiKeyError
from koda_common.settings import KeyringNotInstalledError
from koda_service.services.in_process.catalog import CatalogService
from koda_service.services.in_process.factories import create_registries

if TYPE_CHECKING:
    from koda.llm.models import ModelDefinition
    from koda.llm.registry import ModelRegistry, ProviderRegistry
    from koda_common.settings import SettingsManager


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceStatus:
    is_ready: bool = False
    summary: str = ""


def _ready() -> ServiceStatus:
    return ServiceStatus(
        is_ready=True,
        summary="Ready",
    )


def _not_ready(*, summary: str) -> ServiceStatus:
    return ServiceStatus(
        is_ready=False,
        summary=summary,
    )


def _validate_provider(settings: SettingsManager, provider_registry: ProviderRegistry) -> None:
    provider_registry.get(settings.provider)


def _validate_model(settings: SettingsManager, model_registry: ModelRegistry) -> ModelDefinition:
    return model_registry.get(settings.provider, settings.model)


def _validate_api_key(settings: SettingsManager) -> None:
    api_key = settings.get_api_key(settings.provider)
    if api_key is None:
        raise ApiKeyNotConfiguredError(settings.provider)
    if not api_key.strip():
        raise EmptyApiKeyError(settings.provider)


def _resolve_selection_status(settings: SettingsManager) -> ServiceStatus | None:  # noqa: C901 - allow complex
    catalog = CatalogService(create_registries(), settings)
    connected_provider_ids = {provider.id for provider in catalog.list_connected_providers()}
    if not connected_provider_ids:
        return _not_ready(summary="Provider setup required")
    if settings.provider is not None and settings.provider not in connected_provider_ids:
        return _not_ready(summary=f"Connect {settings.provider} to continue")
    if settings.model is None:
        return _not_ready(summary="Model selection required")

    selectable_model_ids = {
        (model.provider, model.id) for model in catalog.list_selectable_models()
    }
    selected_provider = settings.provider
    if selected_provider is None:
        return _not_ready(summary="Model selection required")
    if (selected_provider, settings.model) not in selectable_model_ids:
        return _not_ready(summary="Selected model unavailable")
    return None


def check_in_process_service_status(settings: SettingsManager) -> ServiceStatus:
    if selection_status := _resolve_selection_status(settings):
        return selection_status
    try:
        registries = create_registries()
        _validate_provider(settings, registries.provider_registry)
        _validate_model(settings, registries.model_registry)
        _validate_api_key(settings)
    except KeyringNotInstalledError:
        return _not_ready(summary="Keychain support is not available")
    except PermissionError:
        return _not_ready(summary="Koda could not access required local files")
    except Exception as error:
        return _not_ready(summary=str(error))
    return _ready()
