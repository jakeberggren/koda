"""Tests for SettingsManager.

These tests are intentionally strict:
- assert call counts (lazy-load + caching)
- cover failure modes (bad store returns, validation)
- avoid testing implementation trivia
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from koda_common.settings.manager import SettingChange, SettingsManager

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


def test_env_overrides_store_for_secrets_backend(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    store = SpySettingsStore({"secrets_backend": "json_file"})
    monkeypatch.setenv("KODA_SECRETS_BACKEND", "keychain")

    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert manager.secrets_backend == "keychain"


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


def test_set_persists_and_notifies_single_change(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    manager.set("provider", "anthropic")

    assert manager.provider == "anthropic"
    assert settings_store.save_calls[-1] == {
        "provider": "anthropic",
        "model": "gpt-5.2",
        "thinking": "none",
        "theme": "dark",
        "show_scrollbar": True,
        "queue_inputs": True,
        "allow_web_search": False,
        "allow_extended_prompt_retention": False,
        "secrets_backend": "json_file",
    }
    assert changes == [
        (SettingChange(name="provider", old_value="openai", new_value="anthropic"),),
    ]


def test_update_commits_all_changes_before_notifying(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    observed: list[tuple[tuple[str, str], tuple[SettingChange, ...]]] = []

    def _record(changes: tuple[SettingChange, ...]) -> None:
        observed.append(((manager.provider, manager.model), changes))

    manager.subscribe(_record)

    manager.update(provider="bergetai", model="zai-org/GLM-4.7")

    assert manager.provider == "bergetai"
    assert manager.model == "zai-org/GLM-4.7"
    assert settings_store.save_calls[-1] == {
        "provider": "bergetai",
        "model": "zai-org/GLM-4.7",
        "thinking": "none",
        "theme": "dark",
        "show_scrollbar": True,
        "queue_inputs": True,
        "allow_web_search": False,
        "allow_extended_prompt_retention": False,
        "secrets_backend": "json_file",
    }
    assert observed == [
        (
            ("bergetai", "zai-org/GLM-4.7"),
            (
                SettingChange(name="provider", old_value="openai", new_value="bergetai"),
                SettingChange(name="model", old_value="gpt-5.2", new_value="zai-org/GLM-4.7"),
            ),
        ),
    ]


def test_invalid_update_raises_without_mutating(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    with pytest.raises(ValidationError):
        manager.set("theme", "bogus")

    assert manager.theme == "dark"
    assert settings_store.save_calls == []


def test_direct_assignment_to_managed_setting_is_rejected(manager: SettingsManager) -> None:
    with pytest.raises(AttributeError, match="provider"):
        manager.provider = "anthropic"


def test_setting_same_value_does_not_notify_or_save(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    manager.set("provider", "openai")

    assert changes == []
    assert settings_store.save_calls == []


def test_unsubscribe_stops_notifications(manager: SettingsManager) -> None:
    changes: list[tuple[SettingChange, ...]] = []
    unsubscribe = manager.subscribe(changes.append)

    unsubscribe()
    manager.set("provider", "anthropic")

    assert changes == []


def test_unsubscribe_is_idempotent(manager: SettingsManager) -> None:
    unsubscribe = manager.subscribe(lambda _changes: None)
    unsubscribe()
    unsubscribe()


def test_multiple_subscribers_all_called(manager: SettingsManager) -> None:
    c1: list[tuple[SettingChange, ...]] = []
    c2: list[tuple[SettingChange, ...]] = []
    manager.subscribe(c1.append)
    manager.subscribe(c2.append)

    manager.set("provider", "anthropic")

    expected = [
        (SettingChange(name="provider", old_value="openai", new_value="anthropic"),),
    ]
    assert c1 == expected
    assert c2 == expected


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

    assert secrets.get_calls == ["openai"]


def test_set_api_key_writes_secrets_store_and_notifies(
    manager: SettingsManager, secrets_store: SpySecretsStore
) -> None:
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    manager.set_api_key("openai", "sk-new")

    assert secrets_store.set_calls == [("openai", "sk-new")]
    assert manager.get_api_key("openai") == "sk-new"
    assert changes == [
        (SettingChange(name="api_keys.openai", old_value=None, new_value="sk-new"),),
    ]


def test_set_api_key_same_cached_value_does_not_notify(
    settings_store: SpySettingsStore,
    secrets_store: SpySecretsStore,
) -> None:
    secrets_store.keys["openai"] = "sk-existing"
    manager = SettingsManager(settings_store=settings_store, secrets_store=secrets_store)
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    assert manager.get_api_key("openai") == "sk-existing"

    manager.set_api_key("openai", "sk-existing")

    assert changes == []
    assert secrets_store.set_calls == [("openai", "sk-existing")]
