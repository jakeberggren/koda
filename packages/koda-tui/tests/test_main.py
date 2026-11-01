from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from koda_common.settings import SettingsStore
from koda_common.settings.errors import (
    SecretsDecodeError,
    SettingsDecodeError,
    SettingsUnknownKeysError,
)
from koda_common.settings.store import JsonObject, SecretsStore
from koda_service.exceptions import StartupConfigurationError
from koda_tui import strings
from koda_tui.app import KodaTuiApp
from koda_tui.main import _fail, load_settings, main

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings.credentials import ProviderCredential


class _FakeSettingsStore(SettingsStore):
    def __init__(self, data: JsonObject | None = None, error: Exception | None = None) -> None:
        self._data = data or {}
        self._error = error

    def load_section(self, name: str) -> JsonObject:
        if self._error is not None:
            raise self._error
        value = self._data.get(name, {})
        return value if isinstance(value, dict) else {}

    def save_section(self, name: str, data: JsonObject) -> None:
        self._data[name] = data


class _FakeSecretsStore(SecretsStore):
    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error
        self.validate_calls = 0

    def validate(self) -> None:
        self.validate_calls += 1
        if self._error is not None:
            raise self._error

    def get_credential(self, provider: str) -> ProviderCredential | None:
        return None

    def set_credential(self, provider: str, credential: ProviderCredential) -> None:
        return

    def delete_credential(self, provider: str) -> None:
        return


class _TelemetryStub:
    def __init__(self) -> None:
        self.settings = None

    def initialize(self, settings) -> None:
        self.settings = settings


def _run_main_with_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
) -> str:
    """Run main with load_settings raising ``error``; it must exit with 1. Returns stderr."""
    monkeypatch.setattr(
        "koda_tui.main.load_settings",
        lambda *_args: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr("koda_tui.main.configure_logging", lambda _config: None)

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    return capsys.readouterr().err


def test_load_settings_raises_settings_error_from_store(tmp_path: Path) -> None:
    error = SettingsDecodeError(
        path=tmp_path / "config.json",
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    with pytest.raises(SettingsDecodeError) as exc_info:
        load_settings(_FakeSettingsStore(error=error), _FakeSecretsStore())

    assert exc_info.value is error


def test_load_settings_raises_secrets_error_from_store(tmp_path: Path) -> None:
    error = SecretsDecodeError(
        path=tmp_path / "secrets.json",
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    with pytest.raises(SecretsDecodeError) as exc_info:
        load_settings(_FakeSettingsStore(), _FakeSecretsStore(error=error))

    assert exc_info.value is error


def test_load_settings_validates_the_secrets() -> None:
    secrets_store = _FakeSecretsStore()

    settings = load_settings(_FakeSettingsStore(), secrets_store)

    assert settings.core is not None
    assert settings.tui is not None
    assert secrets_store.validate_calls == 1


def test_main_runs_the_app_for_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = load_settings(_FakeSettingsStore(), _FakeSecretsStore())
    telemetry = _TelemetryStub()
    monkeypatch.setattr("koda_tui.main.configure_logging", lambda _config: None)
    monkeypatch.setattr("koda_tui.main.load_settings", lambda *_args: settings)
    monkeypatch.setattr("koda_tui.main.LangfuseTelemetry", lambda: telemetry)
    ran: list[KodaTuiApp] = []

    async def _run(app: KodaTuiApp) -> None:
        ran.append(app)

    monkeypatch.setattr(KodaTuiApp, "run", _run)

    main()

    [app] = ran
    assert app.app_settings is settings
    assert app.state.workspace == tmp_path.resolve()
    assert telemetry.settings is settings.core


def test_fail_prints_what_to_fix_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    error = StartupConfigurationError(
        "Invalid configuration",
        details=("theme: Input should be 'auto', 'dark' or 'light'",),
    )

    with pytest.raises(SystemExit) as exc_info:
        _fail(error)

    assert exc_info.value.code == 1
    assert capsys.readouterr().err == (
        f"{strings.App.failed_to_start('Invalid configuration')}\n"
        "- theme: Input should be 'auto', 'dark' or 'light'\n"
    )


def test_main_reports_a_settings_file_that_isnt_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "config.json"
    error = SettingsDecodeError(
        path=path,
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    err = _run_main_with_error(monkeypatch, capsys, error)

    assert f"Settings file is not valid JSON: {path}" in err
    assert "Expecting value at line 1, column 2" in err


def test_main_reports_unknown_settings_keys(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = SettingsUnknownKeysError({"not_a_setting"})
    err = _run_main_with_error(monkeypatch, capsys, error)

    assert "Unknown settings keys: not_a_setting" in err


def test_main_reports_a_secrets_file_that_isnt_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = SecretsDecodeError(
        path=tmp_path / "secrets.json",
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    err = _run_main_with_error(monkeypatch, capsys, error)

    assert err.startswith(strings.App.failed_to_start(""))
