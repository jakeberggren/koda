from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import exceptions

if TYPE_CHECKING:
    from collections.abc import Iterable

    from koda.llm.models import ModelDefinition


class ModelRegistry:
    """Registry for LLM models keyed by provider + model id."""

    def __init__(self) -> None:
        self._models: dict[tuple[str, str], ModelDefinition] = {}

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower()

    def register(self, model_definition: ModelDefinition) -> None:
        provider = self._normalize(model_definition.provider)
        model_id = self._normalize(model_definition.id)
        if not provider or not model_id:
            raise exceptions.ModelConfigurationError

        key = (provider, model_id)
        if key in self._models:
            raise exceptions.ModelAlreadyRegisteredError(
                model_definition.name,
                model_definition.provider,
            )

        self._models[key] = model_definition

    def register_all(self, model_definitions: Iterable[ModelDefinition]) -> None:
        for model_definition in model_definitions:
            self.register(model_definition)

    def get(self, provider: str, model_id: str) -> ModelDefinition:
        normalized_provider = self._normalize(provider)
        normalized_model_id = self._normalize(model_id)
        model_definition = self._models.get((normalized_provider, normalized_model_id))
        if model_definition is None:
            raise exceptions.ModelNotSupportedError(model_id, provider)
        return model_definition

    def supported(self, provider: str | None = None) -> list[ModelDefinition]:
        models = list(self._models.values())
        if provider is not None:
            normalized_provider = self._normalize(provider)
            models = [
                model_definition
                for model_definition in models
                if self._normalize(model_definition.provider) == normalized_provider
            ]
        return sorted(models, key=lambda model_definition: model_definition.id, reverse=True)
