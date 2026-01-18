from koda.providers import exceptions
from koda.providers.openai.adapter import OpenAIAdapter
from koda.providers.openai.provider import OpenAIProvider
from koda.providers.registry import get_provider_registry
from koda_common import SettingsManager


def _create_openai_provider(settings: SettingsManager, model: str | None) -> OpenAIProvider:
    """Factory function for creating OpenAI provider instances."""
    api_key = settings.get_api_key("openai")
    if not api_key:
        raise exceptions.ApiKeyNotConfiguredError("OpenAI")
    return OpenAIProvider(
        api_key=api_key,
        model=model or settings.model,
    )


# Self-register on import
get_provider_registry().register("openai", _create_openai_provider)

__all__ = ["OpenAIAdapter", "OpenAIProvider"]
