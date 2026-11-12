"""Settings errors: a settings or secrets file Koda can't use, and how to fix it."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import json
    from pathlib import Path

    from pydantic import ValidationError


class SettingsError(Exception):
    """What is wrong, in ``summary``, and the particulars, in ``details``."""

    def __init__(self, summary: str, *, details: tuple[str, ...] = ()) -> None:
        super().__init__(summary)
        self.summary = summary
        self.details = details

    def __str__(self) -> str:
        if not self.details:
            return self.summary
        details = "\n".join(f"- {detail}" for detail in self.details)
        return f"{self.summary}\n{details}"


def _not_json(path: Path, error: json.JSONDecodeError) -> tuple[str, tuple[str, ...]]:
    return (
        f"Settings file is not valid JSON: {path}",
        (f"{error.msg} at line {error.lineno}, column {error.colno}",),
    )


_NO_ACCESS = "Koda could not access required local files"


class SettingsLoadError(SettingsError):
    """The settings file can't be loaded."""


class SettingsDecodeError(SettingsLoadError):
    """The settings file is not JSON."""

    def __init__(self, *, path: Path, error: json.JSONDecodeError) -> None:
        summary, details = _not_json(path, error)
        super().__init__(summary, details=details)
        self.path = path
        self.error = error


class SettingsStructureError(SettingsLoadError):
    """The settings JSON is not shaped as expected."""

    def __init__(self, *, path: Path, message: str) -> None:
        super().__init__(message)
        self.path = path


class SettingsPermissionError(SettingsLoadError):
    """The settings file can't be read or written."""

    def __init__(self, *, path: Path, error: PermissionError) -> None:
        super().__init__(_NO_ACCESS, details=(str(error),))
        self.path = path
        self.error = error


class SettingsValidationError(SettingsLoadError):
    """The settings don't satisfy their schema."""

    def __init__(self, error: ValidationError) -> None:
        details = tuple(
            f"{'.'.join(str(part) for part in issue['loc']) or '<root>'}: {issue['msg']}"
            for issue in error.errors(include_url=False)
        )
        super().__init__("Invalid configuration", details=details)
        self.error = error


class SettingsUnknownKeysError(SettingsLoadError):
    """The settings file has keys Koda doesn't know."""

    def __init__(self, keys: set[str]) -> None:
        self.keys = tuple(sorted(keys))
        super().__init__(f"Unknown settings keys: {', '.join(self.keys)}")


class SecretsLoadError(SettingsError):
    """The secrets file can't be loaded."""


class SecretsDecodeError(SecretsLoadError):
    """The secrets file is not JSON."""

    def __init__(self, *, path: Path, error: json.JSONDecodeError) -> None:
        summary, details = _not_json(path, error)
        super().__init__(summary, details=details)
        self.path = path
        self.error = error


class SecretsPermissionError(SecretsLoadError):
    """The secrets file can't be read or written."""

    def __init__(self, *, path: Path, error: PermissionError) -> None:
        super().__init__(_NO_ACCESS, details=(str(error),))
        self.path = path
        self.error = error
