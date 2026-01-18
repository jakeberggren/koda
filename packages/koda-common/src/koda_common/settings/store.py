import json
from pathlib import Path
from typing import Any, Protocol


class SettingsStore(Protocol):
    def load(self) -> dict[str, Any]:
        """Load settings from storage. Returns empty dict if no settings are found."""
        ...

    def save(self, data: dict[str, Any]) -> None:
        """Persist settings to storage."""
        ...


class JsonFileSettingsStore(SettingsStore):
    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".config" / "koda" / "settings.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text())

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))


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
            raise KeyringNotInstalledError from e
        return keyring

    def get_key(self, key: str) -> str | None:
        return self._get_keyring().get_password(self.SERVICE_NAME, key)

    def set_key(self, key: str, value: str) -> None:
        self._get_keyring().set_password(self.SERVICE_NAME, key, value)

    def delete_key(self, key: str) -> None:
        self._get_keyring().delete_password(self.SERVICE_NAME, key)
