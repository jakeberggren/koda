"""Tests for settings store implementations.

Be strict: cover negative paths that otherwise become production bugs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from koda_common.settings import SecretsDecodeError, SettingsDecodeError
from koda_common.settings.store import JsonFileSecretsStore, JsonFileSettingsStore

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

    with pytest.raises(SettingsDecodeError) as exc_info:
        store.load()

    assert exc_info.value.path == path
    assert exc_info.value.error.msg == "Expecting value"


def test_json_store_save_creates_dirs_and_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "config" / "koda" / "koda.json"
    store = JsonFileSettingsStore(path)

    store.save({"provider": "anthropic"})
    assert json.loads(path.read_text()) == {"provider": "anthropic"}

    store.save({"provider": "openai", "model": "gpt-4"})
    assert json.loads(path.read_text()) == {"provider": "openai", "model": "gpt-4"}


def test_json_file_secrets_store_get_returns_none_when_missing(tmp_path: Path) -> None:
    store = JsonFileSecretsStore(tmp_path / "secrets.json")
    assert store.get_key("openai") is None


def test_json_file_secrets_store_set_creates_file_and_persists_value(tmp_path: Path) -> None:
    path = tmp_path / "config" / "koda" / "secrets.json"
    store = JsonFileSecretsStore(path)

    store.set_key("openai", "sk-secret")

    assert json.loads(path.read_text()) == {"openai": "sk-secret"}
    assert store.get_key("openai") == "sk-secret"


def test_json_file_secrets_store_delete_removes_existing_key(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    path.write_text('{"openai": "sk-secret", "anthropic": "sk-other"}')
    store = JsonFileSecretsStore(path)

    store.delete_key("openai")

    assert json.loads(path.read_text()) == {"anthropic": "sk-other"}
    assert store.get_key("openai") is None


def test_json_file_secrets_store_delete_missing_file_is_noop(tmp_path: Path) -> None:
    store = JsonFileSecretsStore(tmp_path / "secrets.json")
    store.delete_key("openai")


def test_json_file_secrets_store_validate_raises_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    path.write_text("not-json")
    store = JsonFileSecretsStore(path)

    with pytest.raises(SecretsDecodeError) as exc_info:
        store.validate()

    assert exc_info.value.path == path
    assert exc_info.value.error.msg == "Expecting value"
