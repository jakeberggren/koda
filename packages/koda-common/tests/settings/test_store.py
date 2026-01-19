"""Tests for settings store implementations.

Be strict: cover negative paths that otherwise become production bugs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from koda_common.settings.store import (
    JsonFileSettingsStore,
    KeyChainSecretsStore,
    KeyringNotInstalledError,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_json_store_load_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    store = JsonFileSettingsStore(tmp_path / "koda.json")
    assert store.load() == {}


def test_json_store_load_parses_contents(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"provider": "anthropic", "model": "claude-3"}')
    store = JsonFileSettingsStore(path)
    assert store.load() == {"provider": "anthropic", "model": "claude-3"}


def test_json_store_load_raises_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text("not-json")
    store = JsonFileSettingsStore(path)

    with pytest.raises(json.JSONDecodeError):
        store.load()


def test_json_store_save_creates_dirs_and_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "config" / "koda" / "koda.json"
    store = JsonFileSettingsStore(path)

    store.save({"provider": "anthropic"})
    assert json.loads(path.read_text()) == {"provider": "anthropic"}

    store.save({"provider": "openai", "model": "gpt-4"})
    assert json.loads(path.read_text()) == {"provider": "openai", "model": "gpt-4"}


def test_keychain_store_get_returns_stored_value(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = "sk-secret"
    monkeypatch.setattr(
        "koda_common.settings.store.KeyChainSecretsStore._get_keyring",
        lambda _self: mock_keyring,
    )

    store = KeyChainSecretsStore()
    assert store.get_key("openai") == "sk-secret"


def test_keychain_store_get_returns_none_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = None
    monkeypatch.setattr(
        "koda_common.settings.store.KeyChainSecretsStore._get_keyring",
        lambda _self: mock_keyring,
    )

    store = KeyChainSecretsStore()
    assert store.get_key("nonexistent") is None


def test_keychain_store_set_and_get_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[str, str] = {}
    mock_keyring = MagicMock()
    mock_keyring.get_password.side_effect = lambda _svc, key: stored.get(key)
    mock_keyring.set_password.side_effect = lambda _svc, key, val: stored.__setitem__(key, val)
    mock_keyring.delete_password.side_effect = lambda _svc, key: stored.pop(key, None)
    monkeypatch.setattr(
        "koda_common.settings.store.KeyChainSecretsStore._get_keyring",
        lambda _self: mock_keyring,
    )

    store = KeyChainSecretsStore()

    assert store.get_key("openai") is None
    store.set_key("openai", "sk-new")
    assert store.get_key("openai") == "sk-new"
    store.delete_key("openai")
    assert store.get_key("openai") is None


def test_keychain_store_raises_keyring_not_installed_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This actually tests the import-error branch of _get_keyring.
    def fake_import(name: str, *args, **kwargs):
        if name == "keyring":
            raise ImportError("nope")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    store = KeyChainSecretsStore()
    with pytest.raises(KeyringNotInstalledError):
        store.get_key("openai")


def test_keyring_not_installed_error_message() -> None:
    assert "koda-common[keychain]" in str(KeyringNotInstalledError())
