from __future__ import annotations

import json

from pydantic import ValidationError

from koda_common.settings import (
    EnvSettings,
    JsonFileSettingsStore,
    KeyChainSecretsStore,
    KeyringNotInstalledError,
    Settings,
    SettingsManager,
)
from koda_common.settings.store import JsonFileSecretsStore, SecretsStore
from koda_tui.bootstrap.errors import StartupConfigurationError, StartupEnvironmentError


def create_secrets_store(settings_store: JsonFileSettingsStore) -> SecretsStore:
    env = EnvSettings()
    backend = env.koda_secrets_backend

    if backend is None:
        settings = Settings.model_validate(settings_store.load())
        backend = settings.secrets_backend

    if backend == "keychain":
        return KeyChainSecretsStore()
    return JsonFileSecretsStore()


def create_settings_manager(
    settings_store: JsonFileSettingsStore | None = None,
) -> SettingsManager:
    settings_store = settings_store or JsonFileSettingsStore()
    try:
        return SettingsManager(
            settings_store=settings_store,
            secrets_store=create_secrets_store(settings_store),
        )
    except json.JSONDecodeError as error:
        raise StartupConfigurationError.from_json_decode_error(
            path=str(settings_store.path),
            error=error,
        ) from error
    except ValidationError as error:
        raise StartupConfigurationError.from_validation_error(error) from error
    except KeyringNotInstalledError as error:
        raise StartupEnvironmentError.from_keyring_error(error) from error
    except PermissionError as error:
        raise StartupEnvironmentError.from_permission_error(error) from error
