"""Tests for SettingsManager.

These tests are intentionally strict:
- assert call counts (lazy-load + caching)
- cover failure modes (bad store returns, validation)
- avoid testing implementation trivia
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from koda_common.settings.manager import SettingsManager

from .conftest import SpySecretsStore, SpySettingsStore


def test_loads_from_store(secrets_store: SpySecretsStore) -> None:
    store = SpySettingsStore({"provider": "anthropic", "model": "claude-3"})
    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)
    assert manager.provider == "anthropic"
    assert manager.model == "claude-3"
    assert store.load_calls == 1


def test_env_overrides_store_for_provider(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    store = SpySettingsStore({"provider": "openai", "model": "gpt-4"})
    monkeypatch.setenv("KODA_PROVIDER", "anthropic")

    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert manager.provider == "anthropic"
    assert manager.model == "gpt-4"


def test_env_overrides_store_for_model(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    store = SpySettingsStore({"provider": "anthropic", "model": "claude-3"})
    monkeypatch.setenv("KODA_MODEL", "claude-3.5")

    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert manager.provider == "anthropic"
    assert manager.model == "claude-3.5"


def test_partial_store_merges_with_defaults(secrets_store: SpySecretsStore) -> None:
    store = SpySettingsStore({"provider": "anthropic"})
    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)
    assert manager.provider == "anthropic"
    assert manager.model == "gpt-5.2"


def test_invalid_store_value_raises_validation_error(secrets_store: SpySecretsStore) -> None:
    # model expects str, not int
    store = SpySettingsStore({"model": 123})
    with pytest.raises(ValidationError):
        SettingsManager(settings_store=store, secrets_store=secrets_store)


def test_setting_attribute_persists_and_notifies(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    changes: list[tuple[str, str, str]] = []
    manager.subscribe(lambda n, o, v: changes.append((n, o, v)))

    manager.provider = "anthropic"

    assert manager.provider == "anthropic"
    # persisted payload must be JSON-friendly
    assert settings_store.save_calls[-1] == {
        "provider": "anthropic",
        "model": "gpt-5.2",
        "theme": "dark",
        "show_scrollbar": True,
        "queue_inputs": True,
    }
    assert changes == [("provider", "openai", "anthropic")]


def test_setting_same_value_does_not_notify(manager: SettingsManager) -> None:
    changes: list[tuple[str, str, str]] = []
    manager.subscribe(lambda n, o, v: changes.append((n, o, v)))

    manager.provider = "openai"

    assert changes == []


def test_unsubscribe_stops_notifications(manager: SettingsManager) -> None:
    changes: list[tuple[str, str, str]] = []
    unsubscribe = manager.subscribe(lambda n, o, v: changes.append((n, o, v)))

    unsubscribe()
    manager.provider = "anthropic"

    assert changes == []


def test_multiple_subscribers_all_called(manager: SettingsManager) -> None:
    c1: list[tuple[str, str, str]] = []
    c2: list[tuple[str, str, str]] = []
    manager.subscribe(lambda n, o, v: c1.append((n, o, v)))
    manager.subscribe(lambda n, o, v: c2.append((n, o, v)))

    manager.provider = "anthropic"

    assert c1 == [("provider", "openai", "anthropic")]
    assert c2 == [("provider", "openai", "anthropic")]


def test_get_api_key_from_env_is_cached_and_does_not_hit_secrets_store(
    monkeypatch: pytest.MonkeyPatch,
    settings_store: SpySettingsStore,
    secrets_store: SpySecretsStore,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

    manager = SettingsManager(settings_store=settings_store, secrets_store=secrets_store)

    assert manager.get_api_key("openai") == "sk-env"
    assert secrets_store.get_calls == []


def test_get_api_key_lazy_loads_and_caches(settings_store: SpySettingsStore) -> None:
    secrets = SpySecretsStore({"openai": "sk-keychain"})
    manager = SettingsManager(settings_store=settings_store, secrets_store=secrets)

    assert manager.get_api_key("openai") == "sk-keychain"
    assert manager.get_api_key("openai") == "sk-keychain"

    # should only call underlying store once due to cache
    assert secrets.get_calls == ["openai"]


def test_set_api_key_writes_secrets_store_and_notifies(
    manager: SettingsManager, secrets_store: SpySecretsStore
) -> None:
    changes: list[tuple[str, str | None, str]] = []
    manager.subscribe(lambda n, o, v: changes.append((n, o, v)))

    manager.set_api_key("openai", "sk-new")

    assert secrets_store.set_calls == [("openai", "sk-new")]
    assert manager.get_api_key("openai") == "sk-new"
    assert changes == [("api_keys.openai", None, "sk-new")]
