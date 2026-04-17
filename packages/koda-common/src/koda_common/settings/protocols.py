from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

type JsonScalar = str | int | float | bool | None
"""Primitive JSON value supported by the settings file."""


type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
"""Recursive JSON value used by the settings document."""


type JsonObject = dict[str, JsonValue]
"""JSON object payload used for settings sections."""


@dataclass(frozen=True, slots=True)
class SettingChange:
    """One committed settings change delivered to subscribers.

    `name` is the field name that changed.
    `old_value` and `new_value` are the committed values exposed by the manager.
    """

    name: str
    old_value: Any
    new_value: Any


type SettingsChangeSet = tuple[SettingChange, ...]
"""Ordered batch of committed settings changes from one update operation."""


type SettingsChangeCallback = Callable[[SettingsChangeSet], None]
"""Subscriber callback invoked after settings changes have been committed."""


class SettingsManagerProtocol(Protocol):
    """Common mutable settings interface shared by the concrete managers.

    This interface intentionally contains only the behavior both managers expose
    today: subscribe to committed changes, set one field, and update multiple
    fields atomically.
    """

    def subscribe(self, callback: SettingsChangeCallback) -> Callable[[], None]:
        """Register a callback and return an idempotent unsubscribe function."""
        ...

    def set(self, name: str, value: object) -> None:
        """Update one field by name."""
        ...

    def update(self, **changes: object) -> None:
        """Atomically update one or more fields."""
        ...


class SettingsStore(Protocol):
    """Persistence interface for sectioned settings documents."""

    def load_section(self, name: str) -> JsonObject:
        """Load one named settings section. Returns an empty object if missing."""
        ...

    def save_section(self, name: str, data: JsonObject) -> None:
        """Persist one section while preserving the rest of the document."""
        ...


class SecretsStore(Protocol):
    """Persistence interface for provider API keys and similar secrets."""

    def validate(self) -> None:
        """Validate that the backing store is readable and correctly configured."""
        ...

    def get_key(self, key: str) -> str | None:
        """Retrieve a secret by key."""
        ...

    def set_key(self, key: str, value: str) -> None:
        """Persist a secret value."""
        ...

    def delete_key(self, key: str) -> None:
        """Delete a persisted secret if it exists."""
        ...
