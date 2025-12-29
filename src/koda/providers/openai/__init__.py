from koda.config.settings import Settings
from koda.providers.openai.client import OpenAIProvider
from koda.providers.registry import get_provider_registry


def _create_openai_provider(settings: Settings, model: str | None) -> OpenAIProvider:
    """Factory function for creating OpenAI provider instances."""
    return OpenAIProvider(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model=model or settings.KODA_DEFAULT_MODEL,
    )


# Self-register on import
get_provider_registry().register("openai", _create_openai_provider)

__all__ = ["OpenAIProvider"]
