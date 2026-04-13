from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from koda_common.logging.config import get_logger
from koda_common.settings.errors import SettingsValidationError
from koda_common.settings.settings import EnvSettings, Settings

if TYPE_CHECKING:
    from koda_common.settings.store import (
        SecretsStore,
        SettingsStore,
    )


@dataclass(slots=True, frozen=True)
class SettingChange:
    name: str
    old_value: Any
    new_value: Any


type SettingsChangeSet = tuple[SettingChange, ...]
type SettingsChangeCallback = Callable[[SettingsChangeSet], None]

# Prefix for env var to settings field mapping
_ENV_PREFIX = "koda_"
_API_KEY_SUFFIX = "_api_key"

log = get_logger(__name__)


class SettingsManager:
    """Manages application settings with layered loading and change notifications.

    Settings fields are accessed as attributes on this class. Adding a new field
    to Settings automatically makes it available here - no manager changes needed.
    """

    def __init__(
        self,
        settings_store: SettingsStore,
        secrets_store: SecretsStore,
    ) -> None:
        self._settings_store = settings_store
        self._secrets_store = secrets_store
        self._env = EnvSettings()
        self._api_key_cache: dict[str, str] = {}
        self._load_api_keys_from_env()
        self._settings = self._load_layered()
        self._callbacks: list[SettingsChangeCallback] = []

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
        try:
            settings = Settings.model_validate(data)
        except ValidationError as error:
            raise SettingsValidationError(error) from error
        log.info("settings_loaded", provider=settings.provider, model=settings.model)
        return settings

    def _save_settings(self) -> None:
        """Persist non-secret settings to file storage."""
        self._settings_store.save(self._settings.model_dump(mode="json"))

    def _notify(self, changes: SettingsChangeSet) -> None:
        """Notify subscribers of committed setting changes."""
        if not changes:
            return
        for callback in tuple(self._callbacks):
            callback(changes)

    def subscribe(self, callback: SettingsChangeCallback) -> Callable[[], None]:
        """Subscribe to setting changes. Returns unsubscribe function."""
        self._callbacks.append(callback)
        unsubscribed = False

        def unsubscribe() -> None:
            nonlocal unsubscribed
            if unsubscribed:
                return
            unsubscribed = True
            with suppress(ValueError):
                self._callbacks.remove(callback)

        return unsubscribe

    def validate_backends(self) -> None:
        """Validate configured storage backends needed by the manager."""
        self._secrets_store.validate()

    def set(self, name: str, value: Any) -> None:
        """Set a single managed setting."""
        self.update(**{name: value})

    def update(self, **changes: Any) -> None:
        """Atomically update managed settings with validation."""
        unknown_fields = [name for name in changes if name not in Settings.model_fields]
        if unknown_fields:
            raise AttributeError(unknown_fields[0])
        if not changes:
            return

        current_settings = self._settings.model_dump()
        merged = current_settings.copy()
        merged.update(changes)
        updated_settings = Settings.model_validate(merged)
        updated_values = updated_settings.model_dump()
        changed_fields = tuple(
            SettingChange(
                name=name,
                old_value=current_settings[name],
                new_value=updated_values[name],
            )
            for name in changes
            if current_settings[name] != updated_values[name]
        )
        if not changed_fields:
            return

        self._settings = updated_settings
        self._save_settings()
        self._notify(changed_fields)
        for change in changed_fields:
            log.info(
                "setting_changed",
                setting=change.name,
                old_value=change.old_value,
                new_value=change.new_value,
            )

    # Dynamic attribute access - forwards to Settings model

    def __getattr__(self, name: str) -> Any:
        """Get a setting value by name."""
        if name in Settings.model_fields:
            return getattr(self._settings, name)
        if name in EnvSettings.model_fields:
            return getattr(self._env, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Reject direct writes to managed settings and allow internal attributes."""
        if name in Settings.model_fields:
            raise AttributeError(name)
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
        old = self.get_api_key(provider)
        self._secrets_store.set_key(provider, key)
        self._api_key_cache[provider] = key
        if old == key:
            # Avoid false-positive service reconfiguration for unchanged keys.
            return
        self._notify((SettingChange(name=f"api_keys.{provider}", old_value=old, new_value=key),))
        log.info("api_key_updated", provider=provider)
