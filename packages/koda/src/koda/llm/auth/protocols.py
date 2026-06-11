from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from koda_common.settings.credentials import OAuthCredential


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
