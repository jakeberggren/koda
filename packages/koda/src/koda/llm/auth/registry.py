from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.auth.codex import CodexOAuthClient, OpenAICodexProviderAuth
from koda.llm.auth.exceptions import (
    AuthAlreadyRegisteredError,
    AuthNameEmptyError,
    AuthNotSupportedError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from koda.llm.auth.protocols import ProviderAuth


def _normalize(value: str) -> str:
    return value.strip().lower()


class ProviderAuthRegistry:
    """Registry mapping OAuth provider ids to provider auth implementations."""

    @classmethod
    def default(cls) -> ProviderAuthRegistry:
        """Build the registry containing Koda's built-in provider auth flows."""

        codex_auth = OpenAICodexProviderAuth(oauth_client=CodexOAuthClient())
        return cls({codex_auth.id: codex_auth})

    def __init__(self, auth_providers: Mapping[str, ProviderAuth] | None = None) -> None:
        self._auth_providers: dict[str, ProviderAuth] = {}
        for auth_id, auth_provider in (auth_providers or {}).items():
            self.register(auth_id, auth_provider)

    def register(self, auth_id: str, auth_provider: ProviderAuth) -> None:
        """Register a provider auth implementation under a case-insensitive id."""

        normalized_auth_id = _normalize(auth_id)
        if not normalized_auth_id:
            raise AuthNameEmptyError
        if normalized_auth_id in self._auth_providers:
            raise AuthAlreadyRegisteredError(normalized_auth_id)
        self._auth_providers[normalized_auth_id] = auth_provider

    def get(self, auth_id: str) -> ProviderAuth:
        """Return the registered provider auth implementation for an auth id."""

        normalized_auth_id = _normalize(auth_id)
        auth_provider = self._auth_providers.get(normalized_auth_id)
        if auth_provider is None:
            raise AuthNotSupportedError(auth_id)
        return auth_provider
