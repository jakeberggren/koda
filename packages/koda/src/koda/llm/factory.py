from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda.llm.apis import LLMApiContext, LLMApiRegistry
from koda.llm.models import ModelDefinition, ProviderDefinition, ThinkingOption

if TYPE_CHECKING:
    from koda.llm.catalog import ModelCatalog
    from koda.llm.models import ProviderConfig, ProviderModelConfig
    from koda.llm.protocols import LLM
    from koda_common.settings import SettingsManager


class LLMFactory:
    """Factory for creating LLM instances from provider/model configurations."""

    def __init__(
        self,
        catalog: ModelCatalog,
        api_registry: LLMApiRegistry | None = None,
    ) -> None:
        self._catalog = catalog
        self._api_registry = api_registry or LLMApiRegistry.default()

    @staticmethod
    def _model_config_to_definition(
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

        return ModelDefinition(
            id=model_id,
            name=model.name,
            provider=provider_id,
            context_window=model.context_window,
            max_output_tokens=model.max_output_tokens,
            thinking_options=thinking_options,
            model_features=model.capabilities,
        )

    def validate_selection(self, provider_id: str, model_id: str) -> None:
        """Validate that a provider/model combination exists."""
        self._catalog.get_provider(provider_id)
        self._catalog.get_model(provider_id, model_id)

    def create(self, settings: SettingsManager) -> LLM:
        """Create an LLM instance from settings."""
        if settings.provider is None:
            raise exceptions.ProviderSelectionMissingError
        if settings.model is None:
            raise exceptions.ModelSelectionMissingError

        provider_id = settings.provider
        model_id = settings.model
        provider = self._catalog.get_provider(provider_id)
        model = self._catalog.get_model(provider_id, model_id)
        api = self._api_registry.get(provider.api)
        return api(
            LLMApiContext(
                provider_id=provider_id,
                provider=provider,
                model=model,
                settings=settings,
            )
        )

    def list_providers(self) -> list[ProviderDefinition]:
        """List all available providers."""
        return [
            ProviderDefinition(id=provider_id, name=provider.name)
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
