from __future__ import annotations

from koda_common.settings import (
    JsonFileSecretsStore,
    JsonFileSettingsStore,
    KeyringNotInstalledError,
    SecretsLoadError,
    SettingsLoadError,
    SettingsManager,
)
from koda_service.exceptions import startup_error_from_settings_error


def create_settings_manager(
    settings_store: JsonFileSettingsStore | None = None,
    secrets_store: JsonFileSecretsStore | None = None,
) -> SettingsManager:
    settings_store = settings_store or JsonFileSettingsStore()
    secrets_store = secrets_store or JsonFileSecretsStore()

    try:
        settings = SettingsManager(
            settings_store=settings_store,
            secrets_store=secrets_store,
        )
        settings.validate_backends()
    except (KeyringNotInstalledError, SecretsLoadError, SettingsLoadError) as error:
        startup_error = startup_error_from_settings_error(error)
        raise startup_error from error
    else:
        return settings
