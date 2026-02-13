from koda.providers import exceptions
from koda.providers.berget.adapter import BergetAIAdapter
from koda.providers.berget.definitions import MODELS
from koda.providers.berget.provider import BergetAIProvider
from koda.providers.registry import get_model_registry, get_provider_registry
from koda_common import SettingsManager


def _create_bergetai_provider(settings: SettingsManager, model: str) -> BergetAIProvider:
    api_key = settings.get_api_key("bergetai")
    if not api_key:
        raise exceptions.ApiKeyNotConfiguredError("BergetAI")
    model_def = get_model_registry().get(model)
    return BergetAIProvider(
        api_key=api_key,
        model=model,
        adapter=BergetAIAdapter(),
        capabilities=model_def.capabilities,
    )


get_provider_registry().register("bergetai", _create_bergetai_provider)
get_model_registry().register_all(MODELS)

__all__ = ["BergetAIAdapter", "BergetAIProvider"]
