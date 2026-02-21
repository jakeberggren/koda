import importlib

from koda.providers import exceptions
from koda.providers.openai.adapter import OpenAIAdapter
from koda.providers.openai.definitions import MODELS
from koda.providers.openai.provider import OpenAIProvider
from koda.providers.registry import get_model_registry, get_provider_registry
from koda_common.logging import get_logger
from koda_common.settings import SettingsManager

logger = get_logger(__name__)


def _resolve_openai_client(settings: SettingsManager):
    if not settings.langfuse_tracing_enabled:
        return importlib.import_module("openai").AsyncOpenAI
    try:
        return importlib.import_module("langfuse.openai").AsyncOpenAI
    except ModuleNotFoundError:
        logger.warning("langfuse_client_unavailable_falling_back_to_openai")
        return importlib.import_module("openai").AsyncOpenAI


def _create_openai_provider(settings: SettingsManager, model: str) -> OpenAIProvider:
    """Factory function for creating OpenAI provider instances."""
    api_key = settings.get_api_key("openai")
    if not api_key:
        raise exceptions.ApiKeyNotConfiguredError("OpenAI")
    model_def = get_model_registry().get(model)
    openai_client = _resolve_openai_client(settings)

    return OpenAIProvider(
        api_key=api_key,
        model=model,
        capabilities=model_def.capabilities,
        client_factory=openai_client,
    )


# Self-register on import
get_provider_registry().register("openai", _create_openai_provider)
get_model_registry().register_all(MODELS)

__all__ = ["OpenAIAdapter", "OpenAIProvider"]
