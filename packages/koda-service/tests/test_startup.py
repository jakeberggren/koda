from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from koda.llm.exceptions import ApiKeyNotConfiguredError
from koda_common.settings.store import JsonFileSettingsStore
from koda_service.exceptions import StartupConfigurationError
from koda_service.startup import create_startup_context

if TYPE_CHECKING:
    from pathlib import Path


def _create_registries() -> object:
    return object()


class _TelemetryStub:
    pass


def test_create_startup_context_reports_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "koda.json"
    path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(
        "koda_service.startup.JsonFileSettingsStore",
        lambda: JsonFileSettingsStore(path),
    )

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_startup_context(tmp_path)

    assert exc_info.value.summary == f"Settings file is not valid JSON: {path}"
    assert "line 1, column 2" in exc_info.value.details[0]


def test_create_startup_context_reports_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "koda.json"
    path.write_text('{"theme": "poo"}', encoding="utf-8")
    monkeypatch.setattr(
        "koda_service.startup.JsonFileSettingsStore",
        lambda: JsonFileSettingsStore(path),
    )

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_startup_context(tmp_path)

    assert exc_info.value.summary == "Invalid configuration"
    assert exc_info.value.details == ("theme: Input should be 'dark' or 'light'",)


def test_create_startup_context_translates_service_configuration_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "koda_service.startup.SettingsManager",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "koda_service.startup.create_registries",
        _create_registries,
    )
    monkeypatch.setattr(
        "koda_service.startup.create_in_process_runtime_factory",
        lambda **_kwargs: (_ for _ in ()).throw(ApiKeyNotConfiguredError("openai")),
    )

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_startup_context(tmp_path)

    assert str(exc_info.value) == "openai API key not configured"


def test_create_startup_context_passes_telemetry_to_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    telemetry = _TelemetryStub()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "koda_service.startup.SettingsManager",
        lambda **_kwargs: SimpleNamespace(),
    )

    monkeypatch.setattr(
        "koda_service.startup.create_registries",
        _create_registries,
    )
    monkeypatch.setattr(
        "koda_service.startup.create_in_process_runtime_factory",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "koda_service.startup.LangfuseTelemetry",
        lambda: telemetry,
    )

    def _fake_service_constructor(*, runtime_factory: object, telemetry: object):
        captured["runtime_factory"] = runtime_factory
        captured["telemetry"] = telemetry
        return SimpleNamespace()

    monkeypatch.setattr(
        "koda_service.startup.InProcessKodaService",
        _fake_service_constructor,
    )

    context = create_startup_context(tmp_path)

    assert context.settings is not None
    assert captured["telemetry"] is telemetry
