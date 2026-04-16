import json
from pathlib import Path
from typing import Any, Protocol

from koda_common.logging.config import get_logger
from koda_common.paths import config_file_path, secrets_file_path
from koda_common.settings.errors import (
    SecretsDecodeError,
    SecretsPermissionError,
    SettingsDecodeError,
    SettingsPermissionError,
)

log = get_logger(__name__)


class SettingsStore(Protocol):
    def load(self) -> dict[str, Any]:
        """Load settings from storage. Returns empty dict if no settings are found."""
        ...

    def save(self, data: dict[str, Any]) -> None:
        """Persist settings to storage."""
        ...


class JsonFileSettingsStore(SettingsStore):
    def __init__(self, path: Path | None = None):
        self.path = path or config_file_path()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            log.debug("settings_file_not_found", path=str(self.path))
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SettingsDecodeError(path=self.path, error=error) from error
        except PermissionError as error:
            raise SettingsPermissionError(path=self.path, error=error) from error
        log.debug("settings_file_loaded", path=str(self.path))
        return data

    def save(self, data: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except PermissionError as error:
            raise SettingsPermissionError(path=self.path, error=error) from error
        log.debug("settings_file_saved", path=str(self.path))


class SecretsStore(Protocol):
    def validate(self) -> None:
        """Validate that the backing store is readable and correctly configured."""
        ...

    def get_key(self, key: str) -> str | None:
        """Retrieve a secret key from the store."""
        ...

    def set_key(self, key: str, value: str) -> None:
        """Store a secret key in the store."""
        ...

    def delete_key(self, key: str) -> None:
        """Delete a secret key from the store."""
        ...


class JsonFileSecretsStore(SecretsStore):
    """Store secrets in a JSON file on disk.

    Secrets are persisted as a JSON object where each top-level key is the
    secret name and each value is the secret value.

    Missing files are treated as empty storage. Parent directories are created
    automatically when persisting data.

    Args:
        file_path: Path to the JSON file used for secret persistence.
    """

    def __init__(self, file_path: Path | None = None) -> None:
        self._file_path = file_path or secrets_file_path()

    def _load_data(self) -> dict[str, str]:
        if not self._file_path.exists():
            return {}
        try:
            return json.loads(self._file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise SecretsDecodeError(path=self._file_path, error=error) from error
        except PermissionError as error:
            raise SecretsPermissionError(path=self._file_path, error=error) from error

    def _save_data(self, data: dict[str, str]) -> None:
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except PermissionError as error:
            raise SecretsPermissionError(path=self._file_path, error=error) from error

    def validate(self) -> None:
        self._load_data()

    def get_key(self, key: str) -> str | None:
        data = self._load_data()
        return data.get(key)

    def set_key(self, key: str, value: str) -> None:
        data = self._load_data()
        data[key] = value
        self._save_data(data)

    def delete_key(self, key: str) -> None:
        data = self._load_data()
        if key in data:
            del data[key]
            self._save_data(data)
