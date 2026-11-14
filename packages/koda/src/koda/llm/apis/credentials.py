from __future__ import annotations

from time import time
from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda.llm.credentials import ApiKeyCredential, OAuthCredential, ProviderCredential

if TYPE_CHECKING:
    from koda.llm.apis.base import LLMApiContext


OAUTH_REFRESH_SKEW_SECONDS = 60


def _credential_key(context: LLMApiContext) -> str:
    """Return the credentials key for a provider connection."""
    return context.connection.credential_key


def _resolve_credential(context: LLMApiContext) -> ProviderCredential:
    """Return the configured provider connection credential or raise a configuration error."""
    credential_key = _credential_key(context)
    credential = context.credentials.get_credential(credential_key)
    if credential is None:
        raise exceptions.LLMConfigurationError(f"{credential_key} credential not configured")
    return credential


def resolve_api_key_credential(context: LLMApiContext) -> str:
    """Return a normalized provider API key or raise a configuration error."""
    credential = _resolve_credential(context)
    if not isinstance(credential, ApiKeyCredential):
        raise exceptions.LLMConfigurationError(
            f"{_credential_key(context)} requires an API key credential"
        )
    normalized_api_key = credential.value.strip()
    if not normalized_api_key:
        raise exceptions.LLMConfigurationError(
            f"{_credential_key(context)} API key cannot be empty"
        )
    return normalized_api_key


def _oauth_needs_refresh(credential: OAuthCredential) -> bool:
    try:
        expires_at = int(credential.expires_at)
    except ValueError:
        return True
    return expires_at <= int(time()) + OAUTH_REFRESH_SKEW_SECONDS


async def resolve_oauth_credential(context: LLMApiContext) -> OAuthCredential:
    """Return a fresh provider OAuth credential or raise a configuration error."""
    credential_key = _credential_key(context)
    credential = _resolve_credential(context)
    if not isinstance(credential, OAuthCredential):
        raise exceptions.LLMConfigurationError(f"{credential_key} requires an OAuth credential")
    if not _oauth_needs_refresh(credential):
        return credential

    oauth = context.connection.oauth
    if oauth is None:
        raise exceptions.LLMConfigurationError(f"{credential_key} has no browser login")
    try:
        refreshed = await oauth.refresh(credential)
    except Exception as error:
        raise exceptions.LLMAuthenticationError(context.connection.provider, error) from error
    context.credentials.set_credential(credential_key, refreshed)
    return refreshed
