from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from importlib.resources import as_file, files
from typing import TYPE_CHECKING

from pydantic import ValidationError

from koda.llm import exceptions
from koda.llm.models import ProvidersConfig
from koda_common.paths import model_overrides_file_path

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm.models import (
        ProviderConfig,
        ProviderConnectionConfig,
        ProviderModelConfig,
    )

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModelCatalogWarning:
    summary: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedModelRoute:
    provider_id: str
    provider: ProviderConfig
    connection_id: str
    connection: ProviderConnectionConfig
    model: ProviderModelConfig


def _normalize(value: str) -> str:
    """Normalize a string for case-insensitive comparison."""
    return value.strip().lower()


class ModelCatalog:
    """JSON-backed provider and model catalog."""

    def __init__(self, providers: dict[str, ProviderConfig]) -> None:
        # Providers are already normalized by _merge_providers
        self._providers = providers
        self._models, self._model_connections = self._index_provider_models(self._providers)

    @staticmethod
    def _load_config(path: Path) -> ProvidersConfig:
        """Load a providers config from a JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProvidersConfig.model_validate(data)

    @staticmethod
    def _index_provider_models(
        providers: dict[str, ProviderConfig],
    ) -> tuple[
        dict[tuple[str, str], ProviderModelConfig],
        dict[tuple[str, str], list[str]],
    ]:
        """Index connection-scoped models by (provider_id, model_id)."""
        models: dict[tuple[str, str], ProviderModelConfig] = {}
        model_connections: dict[tuple[str, str], list[str]] = {}
        for provider_id, provider in providers.items():
            for connection_id, connection in provider.connections.items():
                normalized_connection_id = _normalize(connection_id)
                for model in connection.models:
                    key = (provider_id, _normalize(model.id))
                    models.setdefault(key, model.model_copy(deep=True))
                    model_connections.setdefault(key, [])
                    if normalized_connection_id not in model_connections[key]:
                        model_connections[key].append(normalized_connection_id)
        return models, model_connections

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
            providers[normalized_provider_id] = provider.model_copy(deep=True)
        return providers

    @staticmethod
    def _invalid_user_config_warning(path: Path, error: Exception) -> ModelCatalogWarning:
        """Build a user-facing warning for an invalid user catalog override."""
        return ModelCatalogWarning(
            summary="invalid models.json",
            detail=f"Ignoring {path}: {error}",
        )

    @classmethod
    def from_files(
        cls,
        builtin_path: Path,
        user_path: Path | None = None,
    ) -> tuple[ModelCatalog, list[ModelCatalogWarning]]:
        """Create a catalog from JSON config files."""
        builtin_config = cls._load_config(builtin_path)
        warnings: list[ModelCatalogWarning] = []
        user_config = None
        if user_path and user_path.exists():
            try:
                user_config = cls._load_config(user_path)
            except (json.JSONDecodeError, ValidationError, OSError) as error:
                warning = cls._invalid_user_config_warning(user_path, error)
                warnings.append(warning)
                log.warning("llm_user_models_config_invalid path=%s error=%s", user_path, error)
        return cls(cls._merge_providers(builtin_config, user_config)), warnings

    @classmethod
    def load(cls) -> tuple[ModelCatalog, list[ModelCatalogWarning]]:
        """Load the catalog from the bundled models.json, merged with user overrides if present."""
        models_config = files("koda.llm").joinpath("models.json")
        with as_file(models_config) as builtin_path:
            user_path = model_overrides_file_path()
            return cls.from_files(builtin_path, user_path)

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

    def model_connection_ids(self, provider_id: str, model_id: str) -> list[str]:
        """Return connection ids that expose a provider model, in catalog order."""
        key = (_normalize(provider_id), _normalize(model_id))
        connection_ids = self._model_connections.get(key)
        if connection_ids is None:
            raise exceptions.ModelNotSupportedError(model_id, provider_id)
        return list(connection_ids)

    @staticmethod
    def _prefer_oauth(connection_ids: list[str]) -> list[str]:
        """Prefer OAuth when the same model is available through multiple connections."""
        if "oauth" not in connection_ids:
            return connection_ids
        return [
            "oauth",
            *(connection_id for connection_id in connection_ids if connection_id != "oauth"),
        ]

    def resolve_route(
        self,
        provider_id: str,
        model_id: str,
        *,
        credential_ids: set[str] | None = None,
    ) -> ResolvedModelRoute:
        """Resolve a provider/model selection to a concrete provider connection."""
        normalized_provider_id = _normalize(provider_id)
        provider = self.get_provider(normalized_provider_id)
        model = self.get_model(normalized_provider_id, model_id)
        connection_ids = self._prefer_oauth(
            self.model_connection_ids(normalized_provider_id, model_id)
        )
        connections = {_normalize(k): v for k, v in provider.connections.items()}

        selected_route = connection_ids[0]
        if credential_ids is not None:
            selected_route = next(
                (
                    connection_id
                    for connection_id in connection_ids
                    if f"{normalized_provider_id}:{connection_id}" in credential_ids
                ),
                selected_route,
            )

        return ResolvedModelRoute(
            provider_id=normalized_provider_id,
            provider=provider,
            connection_id=selected_route,
            connection=connections[selected_route],
            model=model,
        )

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
