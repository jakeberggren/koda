import json
from pathlib import Path
from typing import Any, Protocol

from platformdirs import user_config_dir

from koda_common.logging import get_logger

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
        default_path = Path(user_config_dir("koda", appauthor=False)) / "koda.json"
        self.path = path or default_path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            log.debug("settings_file_not_found", path=str(self.path))
            return {}
        data = json.loads(self.path.read_text())
        log.debug("settings_file_loaded", path=str(self.path))
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))
        log.debug("settings_file_saved", path=str(self.path))


class SecretsStore(Protocol):
    def get_key(self, key: str) -> str | None:
        """Retrieve a secret key from the store."""
        ...

    def set_key(self, key: str, value: str) -> None:
        """Store a secret key in the store."""
        ...

    def delete_key(self, key: str) -> None:
        """Delete a secret key from the store."""
        ...


class KeyringNotInstalledError(ImportError):
    """Raised when keyring is not installed."""

    def __init__(self) -> None:
        super().__init__("Install with 'koda-common[keychain]' for keychain support")


class KeyChainSecretsStore(SecretsStore):
    SERVICE_NAME = "koda"

    def _get_keyring(self):
        try:
            import keyring  # noqa: PLC0415 - optional dependency
        except ImportError as e:
            log.warning("keyring_not_installed")
            raise KeyringNotInstalledError from e
        return keyring

    def get_key(self, key: str) -> str | None:
        result = self._get_keyring().get_password(self.SERVICE_NAME, key)
        log.debug("keychain_key_retrieved", key=key, found=result is not None)
        return result

    def set_key(self, key: str, value: str) -> None:
        self._get_keyring().set_password(self.SERVICE_NAME, key, value)
        log.debug("keychain_key_set", key=key)

    def delete_key(self, key: str) -> None:
        self._get_keyring().delete_password(self.SERVICE_NAME, key)
        log.debug("keychain_key_deleted", key=key)
