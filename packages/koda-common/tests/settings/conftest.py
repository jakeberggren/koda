"""Pytest fixtures for settings tests.

Strict fixtures: track calls, avoid global env leakage, and provide easy helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from koda_common.settings.manager import SettingsManager
from koda_common.settings.settings import EnvSettings


@dataclass
class SpySettingsStore:
    """In-memory settings store that tracks calls and can simulate bad returns."""

    initial_data: dict[str, Any] | None = None
    data: dict[str, Any] = field(default_factory=dict)
    load_calls: int = 0
    save_calls: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.data = dict(self.initial_data or {})

    def load(self) -> dict[str, Any]:
        self.load_calls += 1
        return self.data.copy()

    def save(self, data: dict[str, Any]) -> None:
        # store a deep-ish copy
        self.data = data.copy()
        self.save_calls.append(data.copy())


@dataclass
class SpySecretsStore:
    """In-memory secrets store that tracks calls."""

    initial_keys: dict[str, str] | None = None
    keys: dict[str, str] = field(default_factory=dict)
    get_calls: list[str] = field(default_factory=list)
    set_calls: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.keys = dict(self.initial_keys or {})

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
    """Reset singleton and ensure tests never read a .env file."""

    # Prevent surprise .env reads in CI/dev machines.
    monkeypatch.setattr(EnvSettings, "model_config", {"env_file": None})

    # Reset singleton between tests.
    SettingsManager.reset_instance()

    # Clear env vars used by EnvSettings.
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "KODA_PROVIDER",
        "KODA_MODEL",
        "KODA_USE_MOCK_CLIENT",
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
