from __future__ import annotations

import os
from abc import ABC, abstractmethod
from contextlib import suppress
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ValidationError

from koda_common.settings.errors import SettingsUnknownKeysError, SettingsValidationError
from koda_common.settings.protocols import (
    SettingChange,
    SettingsChangeCallback,
    SettingsChangeSet,
    SettingsManagerProtocol,
)
from koda_common.settings.settings import PersistedSettings, Settings
from koda_common.settings.utils import provider_api_key_env_var

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_common.settings.protocols import JsonObject, SecretsStore, SettingsStore


class BaseSettingsManager(SettingsManagerProtocol, ABC):
    """Provide shared subscription behavior for settings managers."""

    def __init__(self) -> None:
        self._callbacks: list[SettingsChangeCallback] = []

    @staticmethod
    def changed_fields(
        previous: BaseModel,
        current: BaseModel,
        names: tuple[str, ...],
    ) -> SettingsChangeSet:
        """Return the committed field changes for the provided names."""

        previous_values = previous.model_dump()
        current_values = current.model_dump()
        return tuple(
            SettingChange(
                name=name,
                old_value=previous_values[name],
                new_value=current_values[name],
            )
            for name in names
            if previous_values[name] != current_values[name]
        )

    def _notify(self, changes: SettingsChangeSet) -> None:
        """Notify subscribers about one committed batch of changes."""

        if not changes:
            return
        for callback in tuple(self._callbacks):
            callback(changes)

    def subscribe(self, callback: SettingsChangeCallback) -> Callable[[], None]:
        """Register a callback and return an unsubscribe function."""

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

    @abstractmethod
    def update(self, **changes: object) -> None:
        """Apply one atomic settings update."""

    def set(self, name: str, value: object) -> None:
        """Update one field by name."""

        self.update(**{name: value})


_CORE_SECTION = "core"


class SettingsManager(BaseSettingsManager):
    """Manage persisted core settings and build effective settings with env precedence."""

    def __init__(
        self,
        settings_store: SettingsStore,
        secrets_store: SecretsStore,
    ) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._secrets_store = secrets_store
        self._api_key_cache: dict[str, str] = {}
        self._secrets_store.validate()
        self._persisted = self._load_persisted_settings()
        self._settings = self._build_effective_settings(self._persisted)

    def __getattr__(self, name: str) -> Any:
        """Expose effective settings fields as manager attributes."""

        if name in Settings.model_fields:
            return getattr(self._settings, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Reject direct writes to managed settings fields."""

        if name != "_settings" and name in Settings.model_fields:
            raise AttributeError(name)
        super().__setattr__(name, value)

    @staticmethod
    def _persisted_data(settings: PersistedSettings) -> dict[str, object]:
        """Convert persisted settings to plain Python data."""

        return settings.model_dump()

    @staticmethod
    def _persisted_json(settings: PersistedSettings) -> JsonObject:
        """Convert persisted settings to JSON-safe data."""

        return cast("JsonObject", settings.model_dump(mode="json"))

    def _load_section_data(self) -> JsonObject:
        """Load and validate the raw core settings section."""

        persisted = self._settings_store.load_section(_CORE_SECTION)
        unknown_keys = set(persisted) - set(PersistedSettings.model_fields)
        if unknown_keys:
            raise SettingsUnknownKeysError(unknown_keys)
        return persisted

    def _load_persisted_settings(self) -> PersistedSettings:
        """Load persisted core settings from the shared settings store."""

        data = self._load_section_data()
        try:
            return PersistedSettings.model_validate(data)
        except ValidationError as error:
            raise SettingsValidationError(error) from error

    def _build_effective_settings(self, persisted: PersistedSettings) -> Settings:
        """Build effective settings from persisted data and environment."""

        try:
            return Settings.model_validate(self._persisted_data(persisted))
        except ValidationError as error:
            raise SettingsValidationError(error) from error

    @staticmethod
    def _validate_change_names(changes: dict[str, object]) -> None:
        """Reject updates for fields that are not persisted core settings."""

        unknown_fields = [name for name in changes if name not in PersistedSettings.model_fields]
        if unknown_fields:
            raise AttributeError(unknown_fields[0])

    def _build_updated_persisted_settings(self, changes: dict[str, object]) -> PersistedSettings:
        """Apply one change batch to persisted settings and validate the result."""

        merged = self._persisted_data(self._persisted)
        merged.update(changes)
        try:
            return PersistedSettings.model_validate(merged)
        except ValidationError as error:
            raise SettingsValidationError(error) from error

    def update(self, **changes: object) -> None:
        if not changes:
            return
        self._validate_change_names(changes)

        updated_persisted = self._build_updated_persisted_settings(changes)
        persisted_changes = self.changed_fields(self._persisted, updated_persisted, tuple(changes))
        if not persisted_changes:
            return

        updated_effective = self._build_effective_settings(updated_persisted)
        effective_changes = self.changed_fields(self._settings, updated_effective, tuple(changes))

        self._persisted = updated_persisted
        self._settings = updated_effective
        self._settings_store.save_section(_CORE_SECTION, self._persisted_json(updated_persisted))
        self._notify(effective_changes)

    def get_api_key(self, provider: str) -> str | None:
        """Return the configured API key for one provider."""

        if provider in self._api_key_cache:
            return self._api_key_cache[provider]

        if key := os.getenv(provider_api_key_env_var(provider)):
            self._api_key_cache[provider] = key
            return key

        if key := self._secrets_store.get_key(provider):
            self._api_key_cache[provider] = key
        return self._api_key_cache.get(provider)

    def set_api_key(self, provider: str, key: str) -> None:
        """Persist one provider API key and notify subscribers if it changed."""

        old = self.get_api_key(provider)
        self._secrets_store.set_key(provider, key)
        self._api_key_cache[provider] = key
        if old == key:
            return
        self._notify((SettingChange(name=f"api_keys.{provider}", old_value=old, new_value=key),))
