from __future__ import annotations

from typing import TYPE_CHECKING

from koda_service.mappers import (
    map_model_definition_to_contract_model_definition,
    map_provider_definition_to_contract_provider_definition,
)

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager
    from koda_service.types.models import ModelDefinition, ProviderDefinition


class CatalogService:
    """Model and provider discovery for the in-process service."""

    def __init__(self, registries, settings: SettingsManager) -> None:
        self._registries = registries
        self._settings = settings

    def list_providers(self) -> list[ProviderDefinition]:
        core_providers = self._registries.provider_registry.supported()
        return [
            map_provider_definition_to_contract_provider_definition(provider)
            for provider in core_providers
        ]

    def list_connected_providers(self) -> list[ProviderDefinition]:
        return [
            provider
            for provider in self.list_providers()
            if self._settings.get_api_key(provider.id)
        ]

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        core_models = self._registries.model_registry.supported(provider)
        return [map_model_definition_to_contract_model_definition(model) for model in core_models]

    def list_selectable_models(self) -> list[ModelDefinition]:
        connected_provider_ids = {provider.id for provider in self.list_connected_providers()}
        if not connected_provider_ids:
            return []
        return [model for model in self.list_models() if model.provider in connected_provider_ids]
