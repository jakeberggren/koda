from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import json
    from pathlib import Path

    from pydantic import ValidationError


class SettingsError(Exception):
    """Base class for koda-common settings failures."""


class SettingsLoadError(SettingsError):
    """Base class for settings configuration load failures."""


class SettingsDecodeError(SettingsLoadError):
    """Raised when a settings file cannot be parsed as JSON."""

    def __init__(self, *, path: Path, error: json.JSONDecodeError) -> None:
        super().__init__(f"Settings file is not valid JSON: {path}")
        self.path = path
        self.error = error


class SettingsPermissionError(SettingsLoadError):
    """Raised when settings storage cannot be accessed."""

    def __init__(self, *, path: Path, error: PermissionError) -> None:
        super().__init__(str(error))
        self.path = path
        self.error = error


class SettingsValidationError(SettingsLoadError):
    """Raised when loaded settings do not satisfy the Settings schema."""

    def __init__(self, error: ValidationError) -> None:
        super().__init__("Invalid configuration")
        self.error = error


class SettingsUnknownKeysError(SettingsLoadError):
    """Raised when persisted settings contain unsupported keys."""

    def __init__(self, keys: set[str]) -> None:
        self.keys = tuple(sorted(keys))
        joined = ", ".join(self.keys)
        super().__init__(f"Unknown settings keys: {joined}")


class SecretsError(SettingsError):
    """Base class for secret-storage failures."""


class SecretsLoadError(SecretsError):
    """Base class for secret backend load failures."""


class SecretsDecodeError(SecretsLoadError):
    """Raised when a secrets file cannot be parsed as JSON."""

    def __init__(self, *, path: Path, error: json.JSONDecodeError) -> None:
        super().__init__(f"Settings file is not valid JSON: {path}")
        self.path = path
        self.error = error


class SecretsPermissionError(SecretsLoadError):
    """Raised when secret storage cannot be accessed."""

    def __init__(self, *, path: Path, error: PermissionError) -> None:
        super().__init__(str(error))
        self.path = path
        self.error = error
