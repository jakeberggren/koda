from collections.abc import Callable
from typing import Any

from koda_common.logging import get_logger
from koda_common.settings.settings import EnvSettings, Settings
from koda_common.settings.store import (
    JsonFileSettingsStore,
    KeyChainSecretsStore,
    SecretsStore,
    SettingsStore,
)

type SettingsChangeCallback = Callable[[str, Any, Any], None]

# Prefix for env var to settings field mapping
_ENV_PREFIX = "koda_"
_API_KEY_SUFFIX = "_api_key"

log = get_logger(__name__)


class SettingsManager:
    """Manages application settings with layered loading and change notifications.

    Settings fields are accessed as attributes on this class. Adding a new field
    to Settings automatically makes it available here - no manager changes needed.
    """

    _instance: "SettingsManager | None" = None

    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        secrets_store: SecretsStore | None = None,
    ) -> None:
        self._settings_store = settings_store or JsonFileSettingsStore()
        self._secrets_store = secrets_store or KeyChainSecretsStore()
        self._env = EnvSettings()
        self._api_key_cache: dict[str, str] = {}
        self._load_api_keys_from_env()
        self._settings = self._load_layered()
        self._callbacks: list[SettingsChangeCallback] = []

    @classmethod
    def get_instance(cls) -> "SettingsManager":
        """Get a singleton instance of the settings manager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    def _load_api_keys_from_env(self) -> None:
        """Load API key overrides from environment into cache."""
        for env_field in EnvSettings.model_fields:
            value = getattr(self._env, env_field)
            if value is not None and env_field.endswith(_API_KEY_SUFFIX):
                provider = env_field.removesuffix(_API_KEY_SUFFIX)
                self._api_key_cache[provider] = value.get_secret_value()
                log.debug("api_key_loaded_from_env", provider=provider)

    def _apply_setting_override(
        self,
        data: dict[str, Any],
        env_field: str,
        value: Any,
    ) -> None:
        """Apply setting override from environment (KODA_<field> -> <field>)."""
        settings_field = env_field.removeprefix(_ENV_PREFIX)
        if settings_field in Settings.model_fields:
            data[settings_field] = value

    def _apply_env_overrides(self, data: dict[str, Any]) -> None:
        """Apply environment variable overrides to settings data."""
        for env_field in EnvSettings.model_fields:
            value = getattr(self._env, env_field)
            if value is not None and env_field.startswith(_ENV_PREFIX):
                self._apply_setting_override(data, env_field, value)

    def _load_layered(self) -> Settings:
        """Load settings: defaults -> file -> env vars."""
        data: dict[str, Any] = Settings().model_dump()
        data.update(self._settings_store.load())
        self._apply_env_overrides(data)
        settings = Settings.model_validate(data)
        log.info("settings_loaded", provider=settings.provider, model=settings.model)
        return settings

    def _save_settings(self) -> None:
        """Persist non-secret settings to file storage."""
        self._settings_store.save(self._settings.model_dump(mode="json"))

    def _notify(self, name: str, old_value: Any, new_value: Any) -> None:
        """Notify subscribers of a setting change."""
        if old_value != new_value:
            for callback in self._callbacks:
                callback(name, old_value, new_value)

    def subscribe(self, callback: SettingsChangeCallback) -> Callable[[], None]:
        """Subscribe to setting changes. Returns unsubscribe function."""
        self._callbacks.append(callback)
        return lambda: self._callbacks.remove(callback)

    # Dynamic attribute access - forwards to Settings model

    def __getattr__(self, name: str) -> Any:
        """Get a setting value by name."""
        if name in Settings.model_fields:
            return getattr(self._settings, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Set a setting value by name, with auto-save and notification."""
        if name in Settings.model_fields:
            old = getattr(self._settings, name)
            setattr(self._settings, name, value)
            self._save_settings()
            self._notify(name, old, value)
            log.info("setting_changed", setting=name, old_value=old, new_value=value)
            return
        super().__setattr__(name, value)

    # API keys - cached from keychain/env

    def get_api_key(self, provider: str) -> str | None:
        """Get API key for a provider. Loads from secrets store lazily if not cached."""
        if provider not in self._api_key_cache and (key := self._secrets_store.get_key(provider)):
            self._api_key_cache[provider] = key
            log.debug("api_key_loaded_from_keychain", provider=provider)
        return self._api_key_cache.get(provider)

    def set_api_key(self, provider: str, key: str) -> None:
        """Set API key for a provider (saves to secrets store)."""
        old = self._api_key_cache.get(provider)
        self._secrets_store.set_key(provider, key)
        self._api_key_cache[provider] = key
        self._notify(f"api_keys.{provider}", old, key)
        log.info("api_key_updated", provider=provider)

    # Flags

    @property
    def koda_backend(self) -> str:
        """Backend kind selected via environment (not persisted)."""
        return self._env.koda_backend
