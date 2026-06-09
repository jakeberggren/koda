from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from koda_common.settings.credentials import OAuthCredential


@dataclass(frozen=True, slots=True, kw_only=True)
class OAuthTokenResponse:
    """Normalized OAuth token endpoint response."""

    access_token: str
    refresh_token: str
    id_token: str
    expires_at: int | None = None
    expires_in: int | None = None


class OAuthTokenClient(Protocol):
    """OAuth token endpoint behavior used by provider auth flows."""

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokenResponse:
        """Exchange an authorization code for OAuth tokens."""
        ...

    async def refresh_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Refresh OAuth tokens using a refresh token."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class OAuthLoginCallbacks:
    """UI hooks used by provider OAuth flows."""

    on_auth_url: Callable[[str], None]
    on_prompt: Callable[[str], Awaitable[str]]


class ProviderAuth(Protocol):
    """Provider-specific OAuth login and token refresh behavior."""

    id: str

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        """Run the provider login flow and return fresh OAuth credentials."""
        ...

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh an existing OAuth credential."""
        ...
