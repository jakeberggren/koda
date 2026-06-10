from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from koda_common.settings.credentials import OAuthCredential

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True, kw_only=True)
class OAuthAuthorizationFlow:
    """Provider authorization URL plus state needed to complete the code flow."""

    url: str
    state: str
    code_verifier: str
    nonce: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class OAuthLoginCallbacks:
    """UI hooks used by provider OAuth flows."""

    on_auth_url: Callable[[str], None]
    on_prompt: Callable[[str], Awaitable[str]]


class OAuthProviderClient(Protocol):
    """Provider-specific OAuth/OIDC client behavior."""

    def create_authorization_flow(self, *, originator: str = "koda") -> OAuthAuthorizationFlow:
        """Create an authorization URL and state for a browser OAuth login."""
        ...

    async def exchange_code(self, code: str, flow: OAuthAuthorizationFlow) -> OAuthCredential:
        """Exchange an authorization code for validated persisted credentials."""
        ...

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh existing OAuth credentials."""
        ...


class ProviderAuth(Protocol):
    """Provider-specific OAuth login and token refresh behavior."""

    id: str

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        """Run the provider login flow and return fresh OAuth credentials."""
        ...

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh an existing OAuth credential."""
        ...
