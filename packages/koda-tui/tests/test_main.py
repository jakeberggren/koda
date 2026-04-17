from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest

from koda_common.settings import SettingsStore
from koda_common.settings.errors import (
    SecretsDecodeError,
    SettingsDecodeError,
    SettingsUnknownKeysError,
)
from koda_common.settings.store import JsonObject, SecretsStore
from koda_service import InProcessAgentConfig
from koda_service.exceptions import StartupConfigurationError
from koda_tui import _report_startup_error, build_app, main

if TYPE_CHECKING:
    from pathlib import Path

    from structlog.stdlib import BoundLogger


class _LoggerStub:
    def error(self, _event: str, **_kwargs: object) -> None:
        return


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

    def get_key(self, key: str) -> str | None:
        return None

    def set_key(self, key: str, value: str) -> None:
        return

    def delete_key(self, key: str) -> None:
        return


class _TelemetryStub:
    def __init__(self) -> None:
        self.settings = None

    def initialize(self, settings) -> None:
        self.settings = settings


def _run_main_with_error(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> tuple[int, list[StartupConfigurationError]]:
    reported: list[StartupConfigurationError] = []

    monkeypatch.setattr(
        "koda_tui.build_app",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    monkeypatch.setattr("koda_tui.configure_logging", lambda _config: None)
    monkeypatch.setattr(
        "koda_tui._report_startup_error",
        lambda raised, _logger: reported.append(raised),
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    return 1, reported


def test_build_app_raises_settings_error_from_store(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    error = SettingsDecodeError(
        path=path,
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    with pytest.raises(SettingsDecodeError) as exc_info:
        build_app(
            workspace_root=tmp_path,
            settings_store=_FakeSettingsStore(error=error),
            secrets_store=_FakeSecretsStore(),
            telemetry=_TelemetryStub(),
            agent_config=InProcessAgentConfig(cwd=tmp_path),
        )

    assert exc_info.value is error


def test_build_app_raises_secrets_error_from_store(tmp_path: Path) -> None:
    path = tmp_path / "secrets.json"
    error = SecretsDecodeError(
        path=path,
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    with pytest.raises(SecretsDecodeError) as exc_info:
        build_app(
            workspace_root=tmp_path,
            settings_store=_FakeSettingsStore(),
            secrets_store=_FakeSecretsStore(error=error),
            telemetry=_TelemetryStub(),
            agent_config=InProcessAgentConfig(cwd=tmp_path),
        )

    assert exc_info.value is error


def test_build_app_creates_application_with_injected_dependencies(tmp_path: Path) -> None:
    telemetry = _TelemetryStub()
    secrets_store = _FakeSecretsStore()

    app = build_app(
        workspace_root=tmp_path,
        settings_store=_FakeSettingsStore(),
        secrets_store=secrets_store,
        telemetry=telemetry,
        agent_config=InProcessAgentConfig(cwd=tmp_path),
    )

    assert app.app_settings is not None
    assert app.service is not None
    assert app.state.workspace_root == tmp_path
    assert secrets_store.validate_calls == 1
    assert telemetry.settings is app.app_settings.core


def test_report_startup_error_logs_and_prints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report_startup_error(
        StartupConfigurationError(
            "Invalid configuration",
            details=("theme: Input should be 'dark' or 'light'",),
        ),
        cast("BoundLogger", _LoggerStub()),
    )

    captured = capsys.readouterr()
    assert captured.err == (
        "Application failed to start (StartupConfigurationError): "
        "Invalid configuration\n- theme: Input should be 'dark' or 'light'\n"
    )


def test_main_maps_settings_errors_to_startup_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "config.json"
    error = SettingsDecodeError(
        path=path,
        error=json.JSONDecodeError("Expecting value", "{", 1),
    )
    exit_code, reported = _run_main_with_error(monkeypatch, error)

    assert exit_code == 1
    assert reported[0].summary == f"Settings file is not valid JSON: {path}"
    assert reported[0].details == ("Expecting value at line 1, column 2",)


def test_main_maps_unknown_settings_keys_to_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = SettingsUnknownKeysError({"not_a_setting"})
    exit_code, reported = _run_main_with_error(monkeypatch, error)

    assert exit_code == 1
    assert reported[0].summary == "Unknown settings keys: not_a_setting"


def test_main_prints_startup_error_and_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exit_code, reported = _run_main_with_error(
        monkeypatch,
        StartupConfigurationError(
            "Invalid configuration",
            details=("theme: Input should be 'dark' or 'light'",),
        ),
    )

    assert exit_code == 1
    assert reported[0].summary == "Invalid configuration"
