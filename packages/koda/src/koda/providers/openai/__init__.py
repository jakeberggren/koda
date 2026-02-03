from koda.providers import exceptions
from koda.providers.openai.adapter import OpenAIAdapter
from koda.providers.openai.definitions import MODELS
from koda.providers.openai.provider import OpenAIProvider
from koda.providers.registry import get_model_registry, get_provider_registry
from koda_common import SettingsManager


def _create_openai_provider(settings: SettingsManager, model: str) -> OpenAIProvider:
    """Factory function for creating OpenAI provider instances."""
    api_key = settings.get_api_key("openai")
    if not api_key:
        raise exceptions.ApiKeyNotConfiguredError("OpenAI")
    model_def = get_model_registry().get(model)
    return OpenAIProvider(
        api_key=api_key,
        model=model,
        capabilities=model_def.capabilities,
    )


# Self-register on import
get_provider_registry().register("openai", _create_openai_provider)
get_model_registry().register_all(MODELS)

__all__ = ["OpenAIAdapter", "OpenAIProvider"]
