from __future__ import annotations

from typing import TYPE_CHECKING

from koda_service.mappers import (
    map_model_definition_to_contract_model_definition,
    map_provider_definition_to_contract_provider_definition,
)

if TYPE_CHECKING:
    from koda_service.types.models import ModelDefinition, ProviderDefinition


class CatalogService:
    """Model and provider discovery for the in-process service."""

    def __init__(self, registries) -> None:
        self._registries = registries

    def list_providers(self) -> list[ProviderDefinition]:
        core_providers = self._registries.provider_registry.supported()
        return [
            map_provider_definition_to_contract_provider_definition(provider)
            for provider in core_providers
        ]

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        core_models = self._registries.model_registry.supported(provider)
        return [map_model_definition_to_contract_model_definition(model) for model in core_models]
