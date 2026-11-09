import json
from pathlib import Path
from typing import cast

import pytest

from koda.llm import Catalog, Credentials, exceptions
from koda.llm.apis.codex import OpenAICodexResponsesAPI
from koda.llm.apis.completions import OpenAICompletionsAPI
from koda_common.settings.credentials import ApiKeyCredential, ProviderCredential


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _credentials(credentials: dict[str, ProviderCredential]) -> Credentials:
    class _Credentials:
        def get_credential(self, key: str) -> ProviderCredential | None:
            return credentials.get(key)

        def set_credential(self, key: str, credential: ProviderCredential) -> None:
            credentials[key] = credential

    return cast("Credentials", _Credentials())


def test_builtin_haiku_uses_binary_extended_thinking() -> None:
    catalog, _warnings = Catalog.load()
    model = catalog.model("anthropic", "claude-haiku-4-5")

    assert [option.id for option in model.thinking_options] == ["none", "enabled"]
    assert [option.label for option in model.thinking_options] == ["Off", "On"]


def test_builtin_bergetai_uses_openai_completions_api() -> None:
    catalog, _warnings = Catalog.load()
    model = catalog.model("bergetai", "google/gemma-4-31B-it")

    [connection] = model.connections
    assert connection.id == "api-key"
    assert connection.auth == "api-key"
    assert connection.api is OpenAICompletionsAPI
    assert connection.base_url == "https://api.berget.ai/v1"
    assert model.max_output_tokens == 128000


def test_builtin_openai_models_are_offered_by_their_connections() -> None:
    catalog, _warnings = Catalog.load()
    oauth = next(c for c in catalog.provider("openai").connections if c.id == "oauth")
    models = {model.id: model for model in catalog.models("openai")}

    assert oauth.auth == "oauth"
    assert oauth.api is OpenAICodexResponsesAPI
    assert oauth.base_url == "https://chatgpt.com/backend-api/codex"
    assert list(models)[:5] == [
        "gpt-5.5",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5.3-codex",
    ]
    assert [c.id for c in models["gpt-5.5"].connections] == ["api-key", "oauth"]
    assert [c.id for c in models["gpt-5.4-nano"].connections] == ["api-key"]


def test_model_connection_prefers_oauth() -> None:
    catalog, _warnings = Catalog.load()
    model = catalog.model("openai", "gpt-5.5")

    assert model.connection(_credentials({})).id == "oauth"


def test_model_connection_uses_the_connection_with_a_credential() -> None:
    catalog, _warnings = Catalog.load()
    model = catalog.model("openai", "gpt-5.5")
    api_key = ApiKeyCredential(type="api_key", value="key")

    assert model.connection(_credentials({"openai:api-key": api_key})).id == "api-key"


def test_unknown_model_is_not_supported() -> None:
    catalog, _warnings = Catalog.load()

    with pytest.raises(exceptions.ModelNotSupportedError):
        catalog.model("openai", "missing")


def test_user_providers_replace_builtin_providers(tmp_path: Path) -> None:
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

    catalog, warnings = Catalog.from_files(builtin_path, user_path)
    assert warnings == []

    provider = catalog.provider(" OPENAI ")
    [connection] = provider.connections
    assert provider.name == "OpenAI Proxy"
    assert connection.base_url == "https://proxy.example/v1"
    assert connection.capabilities == {"reasoning": True}
    assert [model.id for model in catalog.models("openai")] == ["GPT-5.4", "gpt-5.4-nano"]
    model = catalog.model("openai", " gpt-5.4 ")
    assert model.name == "Custom GPT 5.4"
    assert [option.label for option in model.thinking_options] == ["Off", "Low", "Medium", "High"]
    assert catalog.models("anthropic")[0].id == "claude-sonnet-4-6"


def test_user_config_with_unknown_thinking_mode_falls_back_with_warning(tmp_path: Path) -> None:
    builtin_path = tmp_path / "builtin.json"
    user_path = tmp_path / "user.json"
    connection = {"api": "openai-responses", "base_url": "https://api.openai.com/v1"}
    _write_json(
        builtin_path,
        {"providers": {"openai": {"name": "OpenAI", "connections": {"api-key": connection}}}},
    )
    model = {"id": "gpt-5", "name": "GPT-5", "thinking": {"modes": ["unknown"]}}
    _write_json(
        user_path,
        {
            "providers": {
                "openai": {
                    "name": "Proxy",
                    "connections": {"api-key": connection | {"models": [model]}},
                }
            }
        },
    )

    catalog, warnings = Catalog.from_files(builtin_path, user_path)

    assert catalog.provider("openai").name == "OpenAI"
    assert [warning.summary for warning in warnings] == ["invalid models.json"]


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

    catalog, warnings = Catalog.from_files(builtin_path, user_path)

    assert catalog.provider("openai").name == "OpenAI"
    with pytest.raises(exceptions.ProviderNotSupportedError):
        catalog.provider("openrouter")
    assert [warning.summary for warning in warnings] == ["invalid models.json"]


def test_user_config_with_unknown_api_falls_back_with_warning(tmp_path: Path) -> None:
    builtin_path = tmp_path / "builtin.json"
    user_path = tmp_path / "user.json"
    connection = {"api": "openai-responses", "base_url": "https://api.openai.com/v1"}
    _write_json(
        builtin_path,
        {"providers": {"openai": {"name": "OpenAI", "connections": {"api-key": connection}}}},
    )
    unknown = connection | {"api": "unknown-api"}
    _write_json(
        user_path,
        {"providers": {"openai": {"name": "Proxy", "connections": {"api-key": unknown}}}},
    )

    catalog, warnings = Catalog.from_files(builtin_path, user_path)

    assert catalog.provider("openai").name == "OpenAI"
    assert "unknown api 'unknown-api'" in (warnings[0].detail or "")
