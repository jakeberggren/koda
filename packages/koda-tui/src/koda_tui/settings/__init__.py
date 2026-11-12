"""Settings: the agent's settings and the TUI's, stored in ~/.koda/config.json, and the
provider credentials in ~/.koda/secrets.json."""

from koda_tui.settings.core import PersistedSettings, Settings
from koda_tui.settings.errors import (
    SecretsDecodeError,
    SecretsLoadError,
    SecretsPermissionError,
    SettingsDecodeError,
    SettingsError,
    SettingsLoadError,
    SettingsPermissionError,
    SettingsStructureError,
    SettingsUnknownKeysError,
    SettingsValidationError,
)
from koda_tui.settings.manager import BaseSettingsManager, SettingsManager
from koda_tui.settings.protocols import (
    JsonObject,
    SecretsStore,
    SettingChange,
    SettingsChangeCallback,
    SettingsChangeSet,
    SettingsManagerProtocol,
    SettingsStore,
)
from koda_tui.settings.store import JsonFileSecretsStore, JsonFileSettingsStore
from koda_tui.settings.tui import AppSettings, TuiSettings, TuiSettingsManager

__all__ = [
    "AppSettings",
    "BaseSettingsManager",
    "JsonFileSecretsStore",
    "JsonFileSettingsStore",
    "JsonObject",
    "PersistedSettings",
    "SecretsDecodeError",
    "SecretsLoadError",
    "SecretsPermissionError",
    "SecretsStore",
    "SettingChange",
    "Settings",
    "SettingsChangeCallback",
    "SettingsChangeSet",
    "SettingsDecodeError",
    "SettingsError",
    "SettingsLoadError",
    "SettingsManager",
    "SettingsManagerProtocol",
    "SettingsPermissionError",
    "SettingsStore",
    "SettingsStructureError",
    "SettingsUnknownKeysError",
    "SettingsValidationError",
    "TuiSettings",
    "TuiSettingsManager",
]
