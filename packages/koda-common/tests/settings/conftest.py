"""Pytest fixtures for settings tests.

Strict fixtures: track calls, avoid global env leakage, and provide easy helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from koda_common.settings import SecretsStore, Settings, SettingsManager, SettingsStore

if TYPE_CHECKING:
    from koda_common.settings.store import JsonObject


@dataclass
class SpySettingsStore(SettingsStore):
    """In-memory settings store that tracks calls and can simulate bad returns."""

    initial_data: JsonObject | None = None
    data: JsonObject = field(default_factory=dict)
    load_calls: list[str] = field(default_factory=list)
    save_calls: list[tuple[str, JsonObject]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.data = dict(self.initial_data or {})

    def load_section(self, name: str) -> JsonObject:
        self.load_calls.append(name)
        value = self.data.get(name, {})
        return value.copy() if isinstance(value, dict) else {}

    def save_section(self, name: str, data: JsonObject) -> None:
        # store a deep-ish copy
        self.data[name] = data.copy()
        self.save_calls.append((name, data.copy()))


@dataclass
class SpySecretsStore(SecretsStore):
    """In-memory secrets store that tracks calls."""

    initial_keys: dict[str, str] | None = None
    keys: dict[str, str] = field(default_factory=dict)
    get_calls: list[str] = field(default_factory=list)
    set_calls: list[tuple[str, str]] = field(default_factory=list)
    validate_calls: int = 0

    def __post_init__(self) -> None:
        self.keys = dict(self.initial_keys or {})

    def validate(self) -> None:
        self.validate_calls += 1

    def get_key(self, key: str) -> str | None:
        self.get_calls.append(key)
        return self.keys.get(key)

    def set_key(self, key: str, value: str) -> None:
        self.set_calls.append((key, value))
        self.keys[key] = value

    def delete_key(self, key: str) -> None:
        self.keys.pop(key, None)


@pytest.fixture(autouse=True)
def clean_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests never read a .env file and start with clean env vars."""

    # Prevent surprise .env reads in CI/dev machines.
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})

    # Clear env vars used by Settings.
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "BERGETAI_API_KEY",
        "KODA_PROVIDER",
        "KODA_MODEL",
        "KODA_THINKING",
        "KODA_ALLOW_WEB_SEARCH",
        "KODA_ALLOW_EXTENDED_PROMPT_RETENTION",
        "KODA_BASH_EXECUTION_SANDBOX",
        "KODA_BASH_EXECUTION_DOCKER_IMAGE",
        "LANGFUSE_TRACING_ENABLED",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def settings_store() -> SpySettingsStore:
    return SpySettingsStore()


@pytest.fixture
def secrets_store() -> SpySecretsStore:
    return SpySecretsStore()


@pytest.fixture
def manager(settings_store: SpySettingsStore, secrets_store: SpySecretsStore) -> SettingsManager:
    return SettingsManager(settings_store=settings_store, secrets_store=secrets_store)
