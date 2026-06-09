import json
from pathlib import Path
from typing import Any, cast

import pytest

from koda.llm import exceptions
from koda.llm.apis import LLMApiFactory
from koda.llm.apis.registry import LLMApiRegistry
from koda.llm.catalog import ModelCatalog
from koda.llm.factory import LLMFactory
from koda_common.settings.credentials import ProviderCredential


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _api_factory() -> LLMApiFactory:
    return cast("LLMApiFactory", lambda _context: None)


def _context_api_factory(contexts: list[Any]) -> LLMApiFactory:
    def factory(context: Any) -> object:
        contexts.append(context)
        return object()

    return cast("LLMApiFactory", factory)


class _FakeSettings:
    provider = "openai"
    model = "gpt-5.5"

    def __init__(self, credentials: dict[str, ProviderCredential]) -> None:
        self._credentials = credentials
        self.requested_credentials: list[str] = []

    def get_credential(self, provider: str) -> ProviderCredential | None:
        self.requested_credentials.append(provider)
        return self._credentials.get(provider)


def test_llm_api_registry_validates_api_ids() -> None:
    registry = LLMApiRegistry({"anthropic-messages": _api_factory()})

    assert registry.get(" ANTHROPIC-MESSAGES ") is not None

    with pytest.raises(exceptions.ApiNameEmptyError):
        registry.register(" ", _api_factory())

    with pytest.raises(exceptions.ApiAlreadyRegisteredError):
        registry.register("anthropic-messages", _api_factory())

    with pytest.raises(exceptions.ApiNotSupportedError):
        registry.get("missing-api")


def test_builtin_haiku_uses_binary_extended_thinking() -> None:
    catalog, _warnings = ModelCatalog.load()
    factory = LLMFactory(catalog)
    model_definition = next(
        m for m in factory.list_models("anthropic") if m.id == "claude-haiku-4-5"
    )

    assert [option.id for option in model_definition.thinking_options] == ["none", "enabled"]
    assert [option.label for option in model_definition.thinking_options] == ["Off", "On"]


def test_builtin_bergetai_uses_openai_completions_api() -> None:
    registry, _warnings = ModelCatalog.load()
    provider = registry.get_provider("bergetai")
    model = registry.get_model("bergetai", "google/gemma-4-31B-it")

    connection = provider.connections["api-key"]
    assert connection.auth == "api-key"
    assert connection.api == "openai-completions"
    assert connection.base_url == "https://api.berget.ai/v1"
    assert model.max_output_tokens == 128000


def test_builtin_openai_declares_api_key_and_oauth_connections() -> None:
    catalog, _warnings = ModelCatalog.load()
    factory = LLMFactory(catalog)
    openai_models = factory.list_models("openai")
    openai_provider = catalog.get_provider("openai")
    oauth_connection = openai_provider.connections["oauth"]

    assert oauth_connection.auth == "oauth"
    assert oauth_connection.api == "openai-codex-responses"
    assert oauth_connection.base_url == "https://chatgpt.com/backend-api/codex"
    assert catalog.model_connection_ids("openai", "gpt-5.5") == ["api-key", "oauth"]
    assert catalog.resolve_route("openai", "gpt-5.5").connection_id == "oauth"
    assert [model.id for model in openai_models][:5] == [
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5.3-codex",
    ]
    models_by_id = {model.id: model for model in openai_models}
    assert models_by_id["gpt-5.5"].routes == ["api-key", "oauth"]
    assert models_by_id["gpt-5.4-nano"].routes == ["api-key"]


def test_providers_registry_merges_builtin_and_user_configs(tmp_path: Path) -> None:
    builtin_path = tmp_path / "builtin.json"
    user_path = tmp_path / "user.json"
    _write_json(
        builtin_path,
        {
            "providers": {
                "OpenAI": {
                    "name": "OpenAI",
                    "connections": {
                        "api-key": {
                            "auth": "api-key",
                            "api": "openai-responses",
                            "base_url": "https://api.openai.com/v1",
                            "models": [
                                {"id": "gpt-5.4", "name": "GPT 5.4", "context_window": 1000},
                                {"id": "gpt-5.4-mini", "name": "GPT 5.4 mini"},
                            ],
                        }
                    },
                    "capabilities": {"web_search": True, "reasoning": False},
                }
            }
        },
    )
    _write_json(
        user_path,
        {
            "providers": {
                "openai": {
                    "name": "OpenAI Proxy",
                    "connections": {
                        "api-key": {
                            "auth": "api-key",
                            "api": "openai-responses",
                            "base_url": "https://proxy.example/v1",
                            "models": [
                                {
                                    "id": "GPT-5.4",
                                    "name": "Custom GPT 5.4",
                                    "max_output_tokens": 2000,
                                    "thinking": {
                                        "modes": [
                                            "none",
                                            "low",
                                            "medium",
                                            "high",
                                        ],
                                    },
                                },
                                {"id": "gpt-5.4-nano", "name": "GPT 5.4 nano"},
                            ],
                        }
                    },
                    "capabilities": {"reasoning": True},
                    "thinking_modes": {
                        "none": {"label": "Off", "description": ""},
                        "low": {"label": "Low", "description": ""},
                        "medium": {"label": "Medium", "description": ""},
                        "high": {"label": "High", "description": ""},
                    },
                },
                "anthropic": {
                    "name": "Anthropic",
                    "connections": {
                        "api-key": {
                            "auth": "api-key",
                            "api": "anthropic-messages",
                            "base_url": "https://api.anthropic.com",
                            "models": [
                                {
                                    "id": "claude-sonnet-4-6",
                                    "name": "Claude Sonnet 4.6",
                                    "thinking": {
                                        "modes": [
                                            "none",
                                            "high",
                                        ],
                                    },
                                }
                            ],
                        }
                    },
                    "thinking_modes": {
                        "none": {"label": "Off", "description": ""},
                        "high": {"label": "High", "description": ""},
                    },
                },
            }
        },
    )

    registry, warnings = ModelCatalog.from_files(builtin_path, user_path)
    assert warnings == []

    provider = registry.get_provider(" OPENAI ")
    assert provider.name == "OpenAI Proxy"
    assert provider.connections["api-key"].base_url == "https://proxy.example/v1"
    assert provider.capabilities == {"reasoning": True}
    assert [model.id for model in provider.connections["api-key"].models] == [
        "GPT-5.4",
        "gpt-5.4-nano",
    ]
    model = registry.get_model("openai", " gpt-5.4 ")
    assert model.name == "Custom GPT 5.4"
    assert model.thinking.modes == [
        "none",
        "low",
        "medium",
        "high",
    ]
    factory = LLMFactory(registry)
    model_definition = next(m for m in factory.list_models("openai") if m.id == "gpt-5.4")
    provider_definition = next(p for p in factory.list_providers() if p.id == "openai")
    assert provider_definition.auth == "api-key"
    assert [option.label for option in model_definition.thinking_options] == [
        "Off",
        "Low",
        "Medium",
        "High",
    ]
    assert registry.list_models("anthropic")[0][1] == "claude-sonnet-4-6"


def test_invalid_user_config_falls_back_to_builtin_with_warning(tmp_path: Path) -> None:
    builtin_path = tmp_path / "builtin.json"
    user_path = tmp_path / "user.json"
    _write_json(
        builtin_path,
        {
            "providers": {
                "openai": {
                    "name": "OpenAI",
                    "connections": {
                        "api-key": {
                            "auth": "api-key",
                            "api": "openai-responses",
                            "base_url": "https://api.openai.com/v1",
                        }
                    },
                    "models": [{"id": "gpt-5", "name": "GPT-5"}],
                }
            }
        },
    )
    user_path.write_text('{"providers": {"openrouter": ', encoding="utf-8")

    registry, warnings = ModelCatalog.from_files(builtin_path, user_path)

    assert registry.get_provider("openai").name == "OpenAI"
    assert not registry.has_provider("openrouter")
    assert [warning.summary for warning in warnings] == ["invalid models.json"]
