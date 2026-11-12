"""Provider credentials, and where they are stored."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from koda.llm.exceptions import CredentialsError
from koda.paths import credentials_file_path

if TYPE_CHECKING:
    from pathlib import Path


class ApiKeyCredential(BaseModel):
    type: Literal["api_key"]
    value: str

    @property
    def auth_type(self) -> str:
        return "api-key"


class OAuthCredential(BaseModel):
    type: Literal["oauth"]
    access_token: str
    refresh_token: str
    expires_at: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def auth_type(self) -> str:
        return "oauth"


ProviderCredential = Annotated[ApiKeyCredential | OAuthCredential, Field(discriminator="type")]


class Credentials(Protocol):
    """Provider credentials keyed by ``provider:connection``. Written back on OAuth refresh."""

    def get_credential(self, key: str) -> ProviderCredential | None:
        """Return the credential stored under ``key``, if any."""
        ...

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        """Store ``credential`` under ``key``."""
        ...


_FILE = TypeAdapter(dict[str, ProviderCredential])


class JsonCredentialStore:
    """Credentials in a JSON file only the user can read, ``~/.koda/credentials.json`` by
    default. An API key in the environment, such as ``OPENAI_API_KEY``, comes first."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or credentials_file_path()
        self._credentials: dict[str, ProviderCredential] | None = None  # Read on first use.

    def get_credential(self, key: str) -> ProviderCredential | None:
        if api_key := _environment_api_key(key):
            return ApiKeyCredential(type="api_key", value=api_key)
        return self._load().get(key)

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        credentials = {**self._load(), key: credential}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.write_bytes(_FILE.dump_json(credentials, indent=2))
        self._credentials = credentials

    def _load(self) -> dict[str, ProviderCredential]:
        if self._credentials is None:
            try:
                self._credentials = _FILE.validate_json(self.path.read_bytes())
            except FileNotFoundError:
                self._credentials = {}
            except (OSError, ValidationError) as error:
                raise CredentialsError(self.path, error) from error
        return self._credentials


def _environment_api_key(key: str) -> str | None:
    """The API key for ``key`` in the environment: OPENAI_API_KEY for ``openai:api-key``."""
    provider, _, connection = key.partition(":")
    if connection != "api-key":
        return None
    return os.environ.get(f"{provider.upper()}_API_KEY") or None
