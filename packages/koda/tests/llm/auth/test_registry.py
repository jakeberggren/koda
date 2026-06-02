from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda.llm.auth.exceptions import (
    AuthAlreadyRegisteredError,
    AuthNameEmptyError,
    AuthNotSupportedError,
)
from koda.llm.auth.registry import ProviderAuthRegistry

if TYPE_CHECKING:
    from koda.llm.auth.protocols import OAuthLoginCallbacks
    from koda_common.settings.credentials import OAuthCredential


class _ProviderAuth:
    id = "test-auth"

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        _ = callbacks
        raise NotImplementedError

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        return credential


def test_provider_auth_registry_validates_auth_ids() -> None:
    auth = _ProviderAuth()
    registry = ProviderAuthRegistry({"openai:oauth": auth})

    assert registry.get(" OPENAI:OAUTH ") is auth

    with pytest.raises(AuthNameEmptyError):
        registry.register(" ", auth)

    with pytest.raises(AuthAlreadyRegisteredError):
        registry.register("openai:oauth", auth)

    with pytest.raises(AuthNotSupportedError):
        registry.get("missing-auth")


def test_provider_auth_registry_default_contains_codex_auth() -> None:
    registry = ProviderAuthRegistry.default()

    assert registry.get("openai:oauth").id == "openai:oauth"
