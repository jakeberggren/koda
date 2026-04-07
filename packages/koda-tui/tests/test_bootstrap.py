from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from koda.llm.exceptions import ApiKeyNotConfiguredError
from koda_common.settings.store import JsonFileSettingsStore
from koda_tui.bootstrap import KodaRuntimeManager
from koda_tui.bootstrap.errors import StartupConfigurationError
from koda_tui.bootstrap.settings import create_secrets_store, create_settings_manager
from koda_tui.bootstrap.startup import create_startup_context

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings import SettingsManager
    from koda_service.services.in_process.runtime import InProcessKodaRuntime


class _TelemetryStub:
    def __init__(self) -> None:
        self.initialized_with: object | None = None

    def initialize(self, settings: object) -> None:
        self.initialized_with = settings


def test_create_secrets_store_defaults_to_json_file(tmp_path: Path) -> None:
    store = JsonFileSettingsStore(tmp_path / "koda.json")

    secrets_store = create_secrets_store(store)

    assert type(secrets_store).__name__ == "JsonFileSecretsStore"


def test_create_secrets_store_uses_persisted_keychain_backend(tmp_path: Path) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"secrets_backend": "keychain"}', encoding="utf-8")
    store = JsonFileSettingsStore(path)

    secrets_store = create_secrets_store(store)

    assert type(secrets_store).__name__ == "KeyChainSecretsStore"


def test_create_secrets_store_env_override_wins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"secrets_backend": "json_file"}', encoding="utf-8")
    store = JsonFileSettingsStore(path)
    monkeypatch.setenv("KODA_SECRETS_BACKEND", "keychain")

    secrets_store = create_secrets_store(store)

    assert type(secrets_store).__name__ == "KeyChainSecretsStore"


def test_create_settings_manager_reports_invalid_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "koda.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_settings_manager(JsonFileSettingsStore(path))

    assert exc_info.value.summary == f"Settings file is not valid JSON: {path}"
    assert "line 1, column 2" in exc_info.value.details[0]


def test_create_settings_manager_reports_invalid_configuration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"theme": "poo"}', encoding="utf-8")

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_settings_manager(JsonFileSettingsStore(path))

    assert exc_info.value.summary == "Invalid configuration"
    assert exc_info.value.details == ("theme: Input should be 'dark' or 'light'",)


def test_runtime_manager_translates_runtime_configuration_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = KodaRuntimeManager(
        settings=cast("SettingsManager", SimpleNamespace()),
        cwd=tmp_path,
    )

    monkeypatch.setattr(
        "koda_tui.bootstrap.manager.create_runtime",
        lambda **_kwargs: (_ for _ in ()).throw(ApiKeyNotConfiguredError("openai")),
    )

    with pytest.raises(StartupConfigurationError) as exc_info:
        manager.get_runtime()

    assert str(exc_info.value) == "openai API key not configured"


def test_runtime_manager_builds_and_caches_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = SimpleNamespace(
        provider="openai",
        model="gpt-5.2",
        thinking="none",
        allow_web_search=False,
        allow_extended_prompt_retention=False,
    )
    telemetry = _TelemetryStub()
    built_runtime = cast("InProcessKodaRuntime", SimpleNamespace())
    manager = KodaRuntimeManager(
        settings=cast("SettingsManager", settings),
        cwd=tmp_path,
        telemetry=telemetry,
    )

    def _create_runtime(**kwargs):
        current_settings = kwargs["settings"]
        cwd = kwargs["sandbox_dir"]
        assert current_settings is settings
        assert cwd == tmp_path
        telemetry.initialize(current_settings)
        return built_runtime

    monkeypatch.setattr(
        "koda_tui.bootstrap.manager.create_runtime",
        _create_runtime,
    )

    first = manager.get_runtime()
    second = manager.get_runtime()

    assert first is built_runtime
    assert second is built_runtime
    assert telemetry.initialized_with is settings


def test_create_startup_context_uses_local_settings_and_service_factories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = SimpleNamespace()
    catalog_service = SimpleNamespace()
    runtime_manager = SimpleNamespace()

    def _create_settings_manager(_store) -> object:
        return settings

    def _runtime_manager_factory(*, settings: object, cwd: object) -> object:
        assert settings is not None
        assert cwd == tmp_path
        return runtime_manager

    monkeypatch.setattr(
        "koda_tui.bootstrap.startup.create_settings_manager",
        _create_settings_manager,
    )
    monkeypatch.setattr(
        "koda_tui.bootstrap.startup.create_catalog_service",
        lambda current_settings: catalog_service if current_settings is settings else None,
    )
    monkeypatch.setattr(
        "koda_tui.bootstrap.startup.KodaRuntimeManager",
        _runtime_manager_factory,
    )

    context = create_startup_context(tmp_path)

    assert context.settings is settings
    assert context.catalog_service is catalog_service
    assert context.runtime_manager is runtime_manager
