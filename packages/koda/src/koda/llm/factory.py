from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda.llm.apis import LLMApiContext, LLMApiRegistry
from koda.llm.auth.registry import ProviderAuthRegistry
from koda.llm.models import (
    ModelDefinition,
    ProviderConnectionDefinition,
    ProviderDefinition,
    ThinkingOption,
    resolve_thinking_mode,
)

if TYPE_CHECKING:
    from koda.llm.catalog import ModelCatalog
    from koda.llm.models import ProviderConfig, ProviderModelConfig, ThinkingOptionId
    from koda.llm.protocols import LLM, Credentials


class LLMFactory:
    """Factory for creating LLM instances from provider/model configurations."""

    def __init__(
        self,
        catalog: ModelCatalog,
        api_registry: LLMApiRegistry | None = None,
        auth_registry: ProviderAuthRegistry | None = None,
        *,
        tracing: bool = False,
    ) -> None:
        self._catalog = catalog
        self._tracing = tracing
        self._api_registry = api_registry or LLMApiRegistry.default()
        self._auth_registry = auth_registry or ProviderAuthRegistry.default()

    def _model_config_to_definition(
        self,
        provider_id: str,
        model_id: str,
        *,
        provider: ProviderConfig,
        model: ProviderModelConfig,
    ) -> ModelDefinition:
        """Convert a model config to a model definition with thinking options."""
        thinking_options: list[ThinkingOption] = []
        for mode_id in model.thinking.modes:
            mode = provider.thinking_modes.get(mode_id)
            if mode is None:
                raise exceptions.ModelThinkingModeNotConfiguredError(model.id, provider_id, mode_id)
            thinking_options.append(
                ThinkingOption(
                    id=mode_id,
                    label=mode.label,
                    description=mode.description,
                )
            )

        connection_ids = self._catalog.model_connection_ids(provider_id, model_id)
        detail = model.detail

        return ModelDefinition(
            id=model_id,
            name=model.name,
            provider=provider_id,
            detail=detail,
            context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,
            routes=connection_ids,
            thinking_options=thinking_options,
            model_features=model.capabilities,
        )

    def validate_selection(self, provider_id: str, model_id: str) -> None:
        """Validate that a provider/model combination exists."""
        self._catalog.get_provider(provider_id)
        self._catalog.get_model(provider_id, model_id)

    def _configured_credential_ids(
        self,
        credentials: Credentials,
        provider_id: str,
        model_id: str,
    ) -> set[str]:
        normalized_provider_id = provider_id.strip().lower()
        provider = self._catalog.get_provider(normalized_provider_id)
        credential_ids: set[str] = set()
        for connection_id in self._catalog.model_connection_ids(normalized_provider_id, model_id):
            credential_key = f"{normalized_provider_id}:{connection_id}"
            credential = credentials.get_credential(credential_key)
            connection = provider.connections[connection_id]
            if credential is not None and credential.auth_type == connection.auth:
                credential_ids.add(credential_key)
        return credential_ids

    def resolve_route(
        self,
        provider_id: str,
        model_id: str,
        *,
        credential_ids: set[str] | None = None,
    ):
        """Resolve a provider/model selection to a concrete provider connection."""
        return self._catalog.resolve_route(
            provider_id,
            model_id,
            credential_ids=credential_ids,
        )

    def resolve_configured_route(self, provider_id: str, model_id: str, credentials: Credentials):
        """Resolve a provider/model selection to a connection that has credentials."""
        return self._catalog.resolve_route(
            provider_id,
            model_id,
            credential_ids=self._configured_credential_ids(credentials, provider_id, model_id),
        )

    def resolve_thinking(
        self,
        provider_id: str,
        model_id: str,
        credentials: Credentials,
        thinking: ThinkingOptionId,
    ) -> ThinkingOptionId:
        """Resolve ``thinking`` to a mode the selected model supports."""
        route = self.resolve_configured_route(provider_id, model_id, credentials)
        return resolve_thinking_mode(thinking, route.model.thinking.modes)

    async def create(self, provider_id: str, model_id: str, credentials: Credentials) -> LLM:
        """Create an LLM instance for a provider/model selection."""
        route = self.resolve_configured_route(provider_id, model_id, credentials)
        api = self._api_registry.get(route.connection.api)
        return await api(
            LLMApiContext(
                provider_id=route.provider_id,
                provider=route.provider,
                connection_id=route.connection_id,
                connection=route.connection,
                model=route.model,
                credentials=credentials,
                auth_registry=self._auth_registry,
                tracing=self._tracing,
            )
        )

    def list_providers(self) -> list[ProviderDefinition]:
        """List all available providers."""
        return [
            ProviderDefinition(
                id=provider_id,
                name=provider.name,
                description=provider.description,
                auth=next(iter(provider.connections.values())).auth,
                connections=[
                    ProviderConnectionDefinition(
                        id=connection_id,
                        label=connection.label,
                        description=connection.description,
                        auth=connection.auth,
                    )
                    for connection_id, connection in provider.connections.items()
                ],
            )
            for provider_id, provider in self._catalog.list_providers()
        ]

    def list_models(self, provider_id: str | None = None) -> list[ModelDefinition]:
        """List all models, optionally filtered by provider."""
        providers: dict[str, ProviderConfig] = {}
        models: list[ModelDefinition] = []
        for resolved_provider_id, model_id, model in self._catalog.list_models(provider_id):
            if resolved_provider_id not in providers:
                providers[resolved_provider_id] = self._catalog.get_provider(resolved_provider_id)
            models.append(
                self._model_config_to_definition(
                    resolved_provider_id,
                    model_id,
                    provider=providers[resolved_provider_id],
                    model=model,
                )
            )
        return models
