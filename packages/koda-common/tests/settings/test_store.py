"""Tests for settings store implementations.

Be strict: cover negative paths that otherwise become production bugs.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from koda_common.settings import SecretsDecodeError, SettingsDecodeError, SettingsStructureError
from koda_common.settings.store import JsonFileSecretsStore, JsonFileSettingsStore

if TYPE_CHECKING:
    from pathlib import Path


def test_json_store_load_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    store = JsonFileSettingsStore(tmp_path / "koda.json")
    assert store.load_section("core") == {}


def test_json_store_load_parses_section_contents(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"core": {"provider": "anthropic", "model": "claude-3"}}')
    store = JsonFileSettingsStore(path)
    assert store.load_section("core") == {"provider": "anthropic", "model": "claude-3"}


def test_json_store_load_raises_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text("not-json")
    store = JsonFileSettingsStore(path)

    with pytest.raises(SettingsDecodeError) as exc_info:
        store.load_section("core")

    assert exc_info.value.path == path
    assert exc_info.value.error.msg == "Expecting value"


def test_json_store_save_creates_dirs_and_preserves_other_sections(tmp_path: Path) -> None:
    path = tmp_path / "config" / "koda" / "koda.json"
    store = JsonFileSettingsStore(path)

    store.save_section("core", {"provider": "anthropic"})
    assert json.loads(path.read_text()) == {"core": {"provider": "anthropic"}}

    store.save_section("tui", {"theme": "dark"})
    store.save_section("core", {"provider": "openai", "model": "gpt-4"})
    assert json.loads(path.read_text()) == {
        "core": {"provider": "openai", "model": "gpt-4"},
        "tui": {"theme": "dark"},
    }


def test_json_store_load_raises_on_non_object_document(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text('["not", "an", "object"]')
    store = JsonFileSettingsStore(path)

    with pytest.raises(SettingsStructureError) as exc_info:
        store.load_section("core")

    assert exc_info.value.path == path
    assert exc_info.value.message == "Top-level settings JSON must be an object"


def test_json_store_load_raises_on_non_object_section(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"core": "nope"}')
    store = JsonFileSettingsStore(path)

    with pytest.raises(SettingsStructureError) as exc_info:
        store.load_section("core")

    assert exc_info.value.path == path
    assert exc_info.value.message == "Settings section 'core' must be an object"


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
