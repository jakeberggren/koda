from __future__ import annotations

import json
from importlib.resources import as_file, files
from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda.llm.models import ProvidersConfig

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm.models import (
        ProviderConfig,
        ProviderModelConfig,
    )


def _normalize(value: str) -> str:
    """Normalize a string for case-insensitive comparison."""
    return value.strip().lower()


class ModelCatalog:
    """JSON-backed provider and model catalog."""

    def __init__(self, providers: dict[str, ProviderConfig]) -> None:
        # Providers are already normalized by _merge_providers
        self._providers = providers
        self._models = self._index_provider_models(self._providers)

    @staticmethod
    def _load_config(path: Path) -> ProvidersConfig:
        """Load a providers config from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProvidersConfig.model_validate(data)

    @staticmethod
    def _index_provider_models(
        providers: dict[str, ProviderConfig],
    ) -> dict[tuple[str, str], ProviderModelConfig]:
        """Index models by (provider_id, model_id) for fast lookup."""
        return {
            (provider_id, _normalize(model.id)): model
            for provider_id, provider in providers.items()
            for model in provider.models
        }

    @staticmethod
    def _merge_provider(
        builtin_provider: ProviderConfig,
        user_provider: ProviderConfig,
    ) -> ProviderConfig:
        """Merge a user-defined provider config with the builtin config."""
        # Merge models, with user-defined models taking precedence
        models_by_id = {
            _normalize(model.id): model.model_copy(deep=True)
            for model in (*builtin_provider.models, *user_provider.models)
        }
        return builtin_provider.model_copy(
            update={
                "name": user_provider.name,
                "base_url": user_provider.base_url,
                "api": user_provider.api,
                "capabilities": {
                    **builtin_provider.capabilities,
                    **user_provider.capabilities,
                },
                "thinking_modes": {
                    **builtin_provider.thinking_modes,
                    **user_provider.thinking_modes,
                },
                "models": list(models_by_id.values()),
            },
            deep=True,
        )

    @staticmethod
    def _merge_providers(
        builtin_config: ProvidersConfig,
        user_config: ProvidersConfig | None,
    ) -> dict[str, ProviderConfig]:
        """Merge builtin and user provider configs."""
        providers = {
            _normalize(provider_id): provider.model_copy(deep=True)
            for provider_id, provider in builtin_config.providers.items()
        }

        for provider_id, provider in (user_config.providers if user_config else {}).items():
            normalized_provider_id = _normalize(provider_id)
            providers[normalized_provider_id] = (
                ModelCatalog._merge_provider(providers[normalized_provider_id], provider)
                if normalized_provider_id in providers
                else provider.model_copy(deep=True)
            )
        return providers

    @classmethod
    def from_files(
        cls,
        builtin_path: Path,
        user_path: Path | None = None,
    ) -> ModelCatalog:
        """Create a catalog from JSON config files."""
        builtin_config = cls._load_config(builtin_path)
        user_config = cls._load_config(user_path) if user_path and user_path.exists() else None
        return cls(cls._merge_providers(builtin_config, user_config))

    @classmethod
    def from_builtin(cls) -> ModelCatalog:
        """Create a catalog from the bundled models.json."""
        models_config = files("koda.llm").joinpath("models.json")
        with as_file(models_config) as providers_path:
            return cls.from_files(providers_path)

    def get_provider(self, provider_id: str) -> ProviderConfig:
        """Get a provider by ID."""
        provider = self._providers.get(_normalize(provider_id))
        if provider is None:
            raise exceptions.ProviderNotSupportedError(provider_id)
        return provider

    def has_provider(self, provider_id: str | None) -> bool:
        """Check if a provider exists."""
        if provider_id is None:
            return False
        return _normalize(provider_id) in self._providers

    def get_model(self, provider_id: str, model_id: str) -> ProviderModelConfig:
        """Get a model by provider and model ID."""
        model = self._models.get((_normalize(provider_id), _normalize(model_id)))
        if model is None:
            raise exceptions.ModelNotSupportedError(model_id, provider_id)
        return model

    def list_providers(self) -> list[tuple[str, ProviderConfig]]:
        """List all providers."""
        return list(self._providers.items())

    def list_models(
        self,
        provider_id: str | None = None,
    ) -> list[tuple[str, str, ProviderModelConfig]]:
        """List models, optionally filtered by provider."""
        target = _normalize(provider_id) if provider_id is not None else None
        return [
            (resolved_provider_id, model_id, model)
            for (resolved_provider_id, model_id), model in self._models.items()
            if target is None or resolved_provider_id == target
        ]
