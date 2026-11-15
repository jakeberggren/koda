import json
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from koda.llm import Catalog, Credentials, Thinking, exceptions
from koda.llm.apis.codex import OpenAICodexResponsesAPI
from koda.llm.apis.completions import OpenAICompletionsAPI
from koda.llm.auth.codex import OpenAICodexAuth
from koda.llm.credentials import ApiKeyCredential, OAuthCredential, ProviderCredential


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
    catalog, _warnings = Catalog.load(_credentials({}))
    model = catalog.model("anthropic", "claude-haiku-4-5")

    assert [option.id for option in model.thinking.options] == ["none", "enabled"]
    assert [option.label for option in model.thinking.options] == ["Off", "On"]


def test_builtin_bergetai_uses_openai_completions_api() -> None:
    catalog, _warnings = Catalog.load(_credentials({}))
    model = catalog.model("bergetai", "google/gemma-4-31B-it")

    [connection] = model.connections
    assert connection.id == "api-key"
    assert connection.auth == "api-key"
    assert connection.api is OpenAICompletionsAPI
    assert connection.base_url == "https://api.berget.ai/v1"
    assert model.max_output_tokens == 128000


def test_builtin_openai_models_are_offered_by_their_connections() -> None:
    catalog, _warnings = Catalog.load(_credentials({}))
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
    assert [c.id for c in models["gpt-5.5"].connections] == ["oauth", "api-key"]
    assert [c.id for c in models["gpt-5.4-nano"].connections] == ["api-key"]


def _oauth() -> OAuthCredential:
    return OAuthCredential(
        type="oauth",
        access_token="access",  # noqa: S106
        refresh_token="refresh",  # noqa: S106
        expires_at="0",
    )


def _api_key() -> ApiKeyCredential:
    return ApiKeyCredential(type="api_key", value="key")


def test_connected_connection_prefers_oauth() -> None:
    credentials = _credentials({"openai:api-key": _api_key(), "openai:oauth": _oauth()})
    catalog, _warnings = Catalog.load(credentials)
    model = catalog.model("openai", "gpt-5.5")

    assert catalog.connected.connection(model).id == "oauth"
    assert [c.id for c in catalog.connected.connections(model)] == ["oauth", "api-key"]


def test_connected_connection_is_the_one_with_a_credential() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:api-key": _api_key()}))
    model = catalog.model("openai", "gpt-5.5")

    assert catalog.connected.connection(model).id == "api-key"


def test_a_credential_of_the_wrong_kind_does_not_connect() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:oauth": _api_key()}))

    assert catalog.provider("openai") not in catalog.connected


def test_connected_lists_what_the_credentials_reach() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:api-key": _api_key()}))
    openai = catalog.provider("openai")

    assert catalog.connected.providers == [openai]
    assert catalog.connected.models == catalog.models("openai")
    assert openai in catalog.connected
    assert catalog.model("openai", "gpt-5.5") in catalog.connected


def test_connected_follows_the_credentials_as_they_change() -> None:
    store: dict[str, ProviderCredential] = {}
    catalog, _warnings = Catalog.load(_credentials(store))
    connected = catalog.connected

    assert connected.providers == []
    store["openai:api-key"] = _api_key()
    assert connected.providers == [catalog.provider("openai")]


def test_model_without_a_connected_connection_is_not_connected() -> None:
    catalog, _warnings = Catalog.load(_credentials({}))
    model = catalog.model("openai", "gpt-5.5")

    assert model not in catalog.connected
    with pytest.raises(exceptions.ModelNotConnected, match="is not connected"):
        catalog.connected.connection(model)


async def test_connect_requires_a_connected_provider() -> None:
    catalog, _warnings = Catalog.load(_credentials({}))

    with pytest.raises(exceptions.ModelNotConnected):
        await catalog.connect(catalog.model("openai", "gpt-5.5"))


def test_resolve_needs_a_connected_provider() -> None:
    catalog, _warnings = Catalog.load(_credentials({}))

    with pytest.raises(exceptions.NoProviderConnected):
        catalog.resolve("openai", "gpt-5.5")


def test_resolve_needs_a_selected_model() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:api-key": _api_key()}))

    with pytest.raises(exceptions.NoModelSelected):
        catalog.resolve("openai", None)


def test_resolve_needs_a_model_the_catalog_has() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:api-key": _api_key()}))

    with pytest.raises(exceptions.ModelNotFound):
        catalog.resolve("openai", "missing")


def test_resolve_needs_a_connected_model() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:api-key": _api_key()}))

    with pytest.raises(exceptions.ModelNotConnected):
        catalog.resolve("anthropic", "claude-haiku-4-5")


def test_resolve_returns_the_selected_connected_model() -> None:
    catalog, _warnings = Catalog.load(_credentials({"openai:api-key": _api_key()}))

    assert catalog.resolve("openai", "gpt-5.5") == catalog.model("openai", "gpt-5.5")


def test_unknown_model_is_not_supported() -> None:
    catalog, _warnings = Catalog.load(_credentials({}))

    with pytest.raises(exceptions.ModelNotFound, match="is not supported"):
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

    catalog, warnings = Catalog.from_files(_credentials({}), builtin_path, user_path)
    assert warnings == []

    provider = catalog.provider(" OPENAI ")
    [connection] = provider.connections
    assert provider.name == "OpenAI Proxy"
    assert connection.base_url == "https://proxy.example/v1"
    assert connection.capabilities == {"reasoning": True}
    assert [model.id for model in catalog.models("openai")] == ["GPT-5.4", "gpt-5.4-nano"]
    model = catalog.model("openai", " gpt-5.4 ")
    assert model.name == "Custom GPT 5.4"
    assert [option.label for option in model.thinking.options] == ["Off", "Low", "Medium", "High"]
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

    catalog, warnings = Catalog.from_files(_credentials({}), builtin_path, user_path)

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

    catalog, warnings = Catalog.from_files(_credentials({}), builtin_path, user_path)

    assert catalog.provider("openai").name == "OpenAI"
    with pytest.raises(exceptions.LLMConfigurationError, match="is not supported"):
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

    catalog, warnings = Catalog.from_files(_credentials({}), builtin_path, user_path)

    assert catalog.provider("openai").name == "OpenAI"
    assert "unknown api 'unknown-api'" in (warnings[0].detail or "")


async def test_an_oauth_connection_logs_in_through_its_api_s_browser_login() -> None:
    catalog, _ = Catalog.load(_credentials({}))
    connections = {c.id: c for c in catalog.provider("openai").connections}

    assert isinstance(connections["oauth"].oauth, OpenAICodexAuth)
    assert connections["oauth"].auth == "oauth"
    assert connections["api-key"].oauth is None
    with pytest.raises(exceptions.LLMConfigurationError, match="has no browser login"):
        await connections["api-key"].login(Mock())


def test_thinking_moves_to_the_next_level_and_wraps_around() -> None:
    catalog, _ = Catalog.load(_credentials({}))
    model = catalog.model("openai", "gpt-5.5")
    levels = [option.id for option in model.thinking.options]

    assert model.thinking.after(levels[0]) == levels[1]
    assert model.thinking.after(levels[-1]) == levels[0]
    assert model.thinking.after("not-a-level") == levels[1]


def test_a_model_without_levels_can_only_not_think() -> None:
    thinking = Thinking()

    assert [option.id for option in thinking.options] == ["none"]
    assert not thinking.supported
    assert thinking.resolve("high").id == "none"
    assert thinking.after("none") is None


def test_thinking_needs_an_option() -> None:
    with pytest.raises(ValueError, match="at least one option"):
        Thinking(())
