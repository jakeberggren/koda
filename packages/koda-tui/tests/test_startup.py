from __future__ import annotations

import pytest

from koda_common.settings import JsonFileSecretsStore, JsonFileSettingsStore
from koda_service.exceptions import StartupConfigurationError
from koda_tui.startup import create_settings_manager


def test_create_settings_manager_reports_invalid_settings_json(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_settings_manager(
            JsonFileSettingsStore(path),
            JsonFileSecretsStore(tmp_path / "secrets.json"),
        )

    assert exc_info.value.summary == f"Settings file is not valid JSON: {path}"
    assert "line 1, column 2" in exc_info.value.details[0]


def test_create_settings_manager_reports_invalid_secrets_json(tmp_path) -> None:
    path = tmp_path / "secrets.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(StartupConfigurationError) as exc_info:
        create_settings_manager(
            JsonFileSettingsStore(tmp_path / "config.json"),
            JsonFileSecretsStore(path),
        )

    assert exc_info.value.summary == f"Settings file is not valid JSON: {path}"
    assert "line 1, column 2" in exc_info.value.details[0]
