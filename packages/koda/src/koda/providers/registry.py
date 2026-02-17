from collections.abc import Callable, Iterable
from enum import StrEnum, auto

from pydantic import BaseModel, Field

from koda.providers import Provider, exceptions
from koda_common.logging import get_logger
from koda_common.settings import SettingsManager

logger = get_logger(__name__)

type ProviderFactory = Callable[[SettingsManager, str], Provider]


class ProviderRegistry:
    """Registry for provider factories."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        key = name.strip().lower()
        if not key:
            logger.warning("provider_registration_failed_empty_name")
            raise exceptions.ProviderNameEmptyError
        if key in self._factories:
            logger.warning("provider_already_registered", name=key)
            raise exceptions.ProviderAlreadyRegisteredError(key)
        self._factories[key] = factory

    def create(self, name: str, settings: SettingsManager, model: str | None = None) -> Provider:
        key = name.strip().lower()
        factory = self._factories.get(key)
        if factory is None:
            supported = ", ".join(self.supported()) or "(none)"
            logger.warning("provider_not_supported", name=key, supported=supported)
            raise exceptions.ProviderNotSupportedError(key)
        resolved_model = (model.strip() if model and model.strip() else None) or settings.model
        logger.info("provider_created", name=key, model=resolved_model)
        return factory(settings, resolved_model)

    def supported(self) -> list[str]:
        return sorted(self._factories.keys())


class ThinkingLevel(StrEnum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    EXTRA_HIGH = auto()


class ModelCapabilities(StrEnum):
    WEB_SEARCH = "web_search"


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    thinking: set[ThinkingLevel] = Field(default_factory=set)
    capabilities: set[ModelCapabilities] = Field(default_factory=set)


class ModelRegistry:
    """Registry for provider models keyed by model id."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDefinition] = {}

    @staticmethod
    def _normalize_id(model_id: str) -> str:
        return model_id.strip().lower()

    def register(self, model_definition: ModelDefinition) -> None:
        model_id = self._normalize_id(model_definition.id)
        if not model_id:
            logger.warning("model_registration_failed")
            raise exceptions.ModelConfigurationError
        if model_id in self._models:
            logger.warning("model_already_registered", name=model_definition.name)
            raise exceptions.ModelAlreadyRegisteredError(
                model_definition.name,
                model_definition.provider,
            )
        self._models[model_id] = model_definition

    def register_all(self, model_definitions: Iterable[ModelDefinition]) -> None:
        for model_definition in model_definitions:
            self.register(model_definition)

    def get(self, model_id: str) -> ModelDefinition:
        key = self._normalize_id(model_id)
        model = self._models.get(key)
        if model is None:
            supported = ", ".join(m.id for m in self.supported()) or "(none)"
            logger.warning("model_not_supported", name=model_id, supported=supported)
            raise exceptions.ModelNotSupportedError(model_id, "unknown")
        return model

    def supported(self, provider: str | None = None) -> list[ModelDefinition]:
        """Supported models for given provider."""
        models = list(self._models.values())
        if provider:
            key = provider.strip().lower()
            models = [m for m in models if m.provider.lower() == key]
        return sorted(models, key=lambda m: m.id, reverse=True)


_provider_registry = ProviderRegistry()
_model_registry = ModelRegistry()


def get_provider_registry() -> ProviderRegistry:
    return _provider_registry


def get_model_registry() -> ModelRegistry:
    return _model_registry
