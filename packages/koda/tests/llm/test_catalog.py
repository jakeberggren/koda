import json
from pathlib import Path
from typing import cast

import pytest

from koda.llm import exceptions
from koda.llm.apis import LLMApiFactory
from koda.llm.apis.registry import LLMApiRegistry
from koda.llm.catalog import ModelCatalog
from koda.llm.factory import LLMFactory


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _api_factory() -> LLMApiFactory:
    return cast("LLMApiFactory", lambda _context: None)


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

    assert provider.api == "openai-completions"
    assert provider.base_url == "https://api.berget.ai/v1"
    assert model.max_output_tokens == 128000


def test_providers_registry_merges_builtin_and_user_configs(tmp_path: Path) -> None:
    builtin_path = tmp_path / "builtin.json"
    user_path = tmp_path / "user.json"
    _write_json(
        builtin_path,
        {
            "providers": {
                "OpenAI": {
                    "name": "OpenAI",
                    "base_url": "https://api.openai.com/v1",
                    "api": "openai-responses",
                    "capabilities": {"web_search": True, "reasoning": False},
                    "models": [
                        {"id": "gpt-5.4", "name": "GPT 5.4", "context_window": 1000},
                        {"id": "gpt-5.4-mini", "name": "GPT 5.4 mini"},
                    ],
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
                    "base_url": "https://proxy.example/v1",
                    "api": "openai-responses",
                    "capabilities": {"reasoning": True},
                    "thinking_modes": {
                        "none": {"label": "Off", "description": ""},
                        "low": {"label": "Low", "description": ""},
                        "medium": {"label": "Medium", "description": ""},
                        "high": {"label": "High", "description": ""},
                    },
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
                },
                "anthropic": {
                    "name": "Anthropic",
                    "base_url": "https://api.anthropic.com",
                    "api": "anthropic-messages",
                    "thinking_modes": {
                        "none": {"label": "Off", "description": ""},
                        "high": {"label": "High", "description": ""},
                    },
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
                },
            }
        },
    )

    registry, warnings = ModelCatalog.from_files(builtin_path, user_path)
    assert warnings == []

    provider = registry.get_provider(" OPENAI ")
    assert provider.name == "OpenAI Proxy"
    assert provider.base_url == "https://proxy.example/v1"
    assert provider.capabilities == {"web_search": True, "reasoning": True}
    assert [model.id for model in provider.models] == [
        "GPT-5.4",
        "gpt-5.4-mini",
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
                    "base_url": "https://api.openai.com/v1",
                    "api": "openai-responses",
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
