"""Tests for SettingsManager.

These tests focus on the public behavior:
- persisted core settings live under the ``core`` config section
- env overrides win for effective values but are not persisted
- updates notify on effective changes only
"""

from __future__ import annotations

import pytest

from koda_common.settings import (
    SettingChange,
    SettingsManager,
    SettingsUnknownKeysError,
    SettingsValidationError,
)

from .conftest import SpySecretsStore, SpySettingsStore


def test_loads_from_core_section(secrets_store: SpySecretsStore) -> None:
    store = SpySettingsStore({"core": {"provider": "anthropic", "model": "claude-3"}})
    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)
    assert manager.provider == "anthropic"
    assert manager.model == "claude-3"
    assert store.load_calls == ["core"]


def test_env_overrides_store_for_provider(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    store = SpySettingsStore({"core": {"provider": "openai", "model": "gpt-4"}})
    monkeypatch.setenv("KODA_PROVIDER", "anthropic")

    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert manager.provider == "anthropic"
    assert manager.model == "gpt-4"


def test_partial_store_merges_with_defaults(secrets_store: SpySecretsStore) -> None:
    store = SpySettingsStore({"core": {"provider": "anthropic"}})
    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)
    assert manager.provider == "anthropic"
    assert manager.model is None


def test_invalid_store_value_raises_settings_validation_error(
    secrets_store: SpySecretsStore,
) -> None:
    store = SpySettingsStore({"core": {"model": 123}})
    with pytest.raises(SettingsValidationError):
        SettingsManager(settings_store=store, secrets_store=secrets_store)


def test_unknown_persisted_setting_raises_settings_unknown_keys_error(
    secrets_store: SpySecretsStore,
) -> None:
    store = SpySettingsStore({"core": {"not_a_setting": 123}})

    with pytest.raises(SettingsUnknownKeysError) as exc_info:
        SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert exc_info.value.keys == ("not_a_setting",)


def test_initialization_validates_secrets_store(
    secrets_store: SpySecretsStore,
) -> None:
    SettingsManager(settings_store=SpySettingsStore(), secrets_store=secrets_store)

    assert secrets_store.validate_calls == 1


def test_set_persists_core_section_and_notifies_single_change(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    manager.set("provider", "anthropic")

    assert manager.provider == "anthropic"
    assert settings_store.save_calls[-1] == (
        "core",
        {
            "provider": "anthropic",
            "model": None,
            "thinking": "none",
            "allow_web_search": False,
            "allow_extended_prompt_retention": False,
            "bash_execution_sandbox": "host",
            "bash_execution_docker_image": None,
        },
    )
    assert changes == [
        (SettingChange(name="provider", old_value=None, new_value="anthropic"),),
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
    assert settings_store.save_calls[-1] == (
        "core",
        {
            "provider": "bergetai",
            "model": "zai-org/GLM-4.7",
            "thinking": "none",
            "allow_web_search": False,
            "allow_extended_prompt_retention": False,
            "bash_execution_sandbox": "host",
            "bash_execution_docker_image": None,
        },
    )
    assert observed == [
        (
            ("bergetai", "zai-org/GLM-4.7"),
            (
                SettingChange(name="provider", old_value=None, new_value="bergetai"),
                SettingChange(name="model", old_value=None, new_value="zai-org/GLM-4.7"),
            ),
        ),
    ]


def test_env_override_is_not_written_back_on_unrelated_save(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    monkeypatch.setenv("KODA_PROVIDER", "openai")
    store = SpySettingsStore({"core": {"provider": "anthropic", "thinking": "none"}})
    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    manager.set("thinking", "high")

    assert manager.provider == "openai"
    assert store.save_calls[-1] == (
        "core",
        {
            "provider": "anthropic",
            "model": None,
            "thinking": "high",
            "allow_web_search": False,
            "allow_extended_prompt_retention": False,
            "bash_execution_sandbox": "host",
            "bash_execution_docker_image": None,
        },
    )


def test_env_override_blocks_effective_change_notifications(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    monkeypatch.setenv("KODA_PROVIDER", "openai")
    store = SpySettingsStore({"core": {"provider": "anthropic"}})
    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    manager.set("provider", "bergetai")

    assert manager.provider == "openai"
    assert changes == []


def test_env_overrides_store_for_bash_execution_sandbox(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    store = SpySettingsStore({"core": {"bash_execution_sandbox": "host"}})
    monkeypatch.setenv("KODA_BASH_EXECUTION_SANDBOX", "docker")
    monkeypatch.setenv("KODA_BASH_EXECUTION_DOCKER_IMAGE", "custom-sandbox:dev")

    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert manager.bash_execution_sandbox == "docker"


def test_env_overrides_store_for_bash_execution_docker_image(
    monkeypatch: pytest.MonkeyPatch, secrets_store: SpySecretsStore
) -> None:
    store = SpySettingsStore({"core": {"bash_execution_docker_image": "custom-sandbox:base"}})
    monkeypatch.setenv("KODA_BASH_EXECUTION_DOCKER_IMAGE", "custom-sandbox:dev")

    manager = SettingsManager(settings_store=store, secrets_store=secrets_store)

    assert manager.bash_execution_docker_image == "custom-sandbox:dev"


def test_docker_sandbox_requires_bash_execution_docker_image(
    secrets_store: SpySecretsStore,
) -> None:
    store = SpySettingsStore({"core": {"bash_execution_sandbox": "docker"}})

    with pytest.raises(SettingsValidationError):
        SettingsManager(settings_store=store, secrets_store=secrets_store)


def test_invalid_update_raises_without_mutating(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    with pytest.raises(SettingsValidationError):
        manager.set("provider", 123)

    assert manager.provider is None
    assert settings_store.save_calls == []


def test_direct_assignment_to_managed_setting_is_rejected(manager: SettingsManager) -> None:
    with pytest.raises(AttributeError, match="provider"):
        manager.provider = "anthropic"


def test_setting_same_value_does_not_notify_or_save(
    manager: SettingsManager, settings_store: SpySettingsStore
) -> None:
    changes: list[tuple[SettingChange, ...]] = []
    manager.subscribe(changes.append)

    manager.set("provider", None)

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
        (SettingChange(name="provider", old_value=None, new_value="anthropic"),),
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
    secrets = SpySecretsStore({"openai": "sk-stored"})
    manager = SettingsManager(settings_store=settings_store, secrets_store=secrets)

    assert manager.get_api_key("openai") == "sk-stored"
    assert manager.get_api_key("openai") == "sk-stored"

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
