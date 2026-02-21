import importlib

from koda.providers import exceptions
from koda.providers.berget.adapter import BergetAIAdapter
from koda.providers.berget.definitions import MODELS
from koda.providers.berget.provider import BergetAIProvider
from koda.providers.registry import get_model_registry, get_provider_registry
from koda_common import get_logger
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


def _create_bergetai_provider(settings: SettingsManager, model: str) -> BergetAIProvider:
    api_key = settings.get_api_key("bergetai")
    if not api_key:
        raise exceptions.ApiKeyNotConfiguredError("BergetAI")
    model_def = get_model_registry().get(model)
    openai_client = _resolve_openai_client(settings)

    return BergetAIProvider(
        api_key=api_key,
        model=model,
        adapter=BergetAIAdapter(),
        capabilities=model_def.capabilities,
        client_factory=openai_client,
    )


get_provider_registry().register("bergetai", _create_bergetai_provider)
get_model_registry().register_all(MODELS)

__all__ = ["BergetAIAdapter", "BergetAIProvider"]
