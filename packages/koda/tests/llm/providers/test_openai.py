from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from openai import AsyncOpenAI

from koda.llm.exceptions import (
    ApiKeyNotConfiguredError,
    EmptyApiKeyError,
    ModelNotSupportedError,
)
from koda.llm.providers.openai import (
    OPENAI_MODELS,
    OpenAILLMProvider,
    OpenAILLMProviderConfig,
    create_openai_llm,
)
from koda.llm.registry import ModelRegistry

if TYPE_CHECKING:
    from koda.llm.drivers import ResponsesDriver
    from koda_common.settings import SettingsManager


class DummyClient:
    def __init__(self, **_kwargs: object) -> None:
        return


def _model_registry() -> ModelRegistry:
    registry = ModelRegistry()
    registry.register_all(OPENAI_MODELS)
    return registry


def _client_factory() -> Callable[..., AsyncOpenAI]:
    return cast("Callable[..., AsyncOpenAI]", DummyClient)


def test_from_config_rejects_blank_api_key() -> None:
    with pytest.raises(EmptyApiKeyError) as exc_info:
        OpenAILLMProvider.from_config(
            OpenAILLMProviderConfig(api_key="   ", model="gpt-5.2"),
            client_factory=_client_factory(),
            model_registry=_model_registry(),
        )

    assert str(exc_info.value) == "openai API key cannot be empty"


def test_from_config_validates_model_eagerly() -> None:
    with pytest.raises(ModelNotSupportedError):
        OpenAILLMProvider.from_config(
            OpenAILLMProviderConfig(api_key="test-key", model="bogus"),
            client_factory=_client_factory(),
            model_registry=_model_registry(),
        )


def test_from_config_normalizes_api_key_and_model() -> None:
    provider = OpenAILLMProvider.from_config(
        OpenAILLMProviderConfig(api_key=" test-key ", model=" GPT-5.2 "),
        client_factory=_client_factory(),
        model_registry=_model_registry(),
    )
    driver = cast("ResponsesDriver", provider.driver)

    assert provider.model == "gpt-5.2"
    assert driver.config.api_key == "test-key"
    assert driver.config.model == "gpt-5.2"


def test_create_openai_llm_rejects_missing_api_key() -> None:
    settings = SimpleNamespace(
        model="gpt-5.2",
        langfuse_tracing_enabled=False,
        get_api_key=lambda _provider: None,
    )

    with pytest.raises(ApiKeyNotConfiguredError) as exc_info:
        create_openai_llm(cast("SettingsManager", settings), _model_registry())

    assert str(exc_info.value) == "openai API key not configured"
