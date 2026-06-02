from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda_common.settings.credentials import ApiKeyCredential, OAuthCredential, ProviderCredential

if TYPE_CHECKING:
    from koda.llm.apis.base import LLMApiContext


def _credential_key(context: LLMApiContext) -> str:
    """Return the settings key for a provider connection credential."""
    return f"{context.provider_id}:{context.connection_id}"


def _resolve_credential(context: LLMApiContext) -> ProviderCredential:
    """Return the configured provider connection credential or raise a configuration error."""
    credential_key = _credential_key(context)
    credential = context.settings.get_credential(credential_key)
    if credential is None:
        raise exceptions.ProviderCredentialNotConfiguredError(credential_key)
    return credential


def resolve_api_key_credential(context: LLMApiContext) -> str:
    """Return a normalized provider API key or raise a configuration error."""
    credential = _resolve_credential(context)
    if not isinstance(credential, ApiKeyCredential):
        raise exceptions.ApiKeyCredentialRequiredError(_credential_key(context))
    normalized_api_key = credential.value.strip()
    if not normalized_api_key:
        raise exceptions.EmptyApiKeyError(_credential_key(context))
    return normalized_api_key


def resolve_oauth_credential(context: LLMApiContext) -> OAuthCredential:
    """Return the configured provider OAuth credential or raise a configuration error."""
    credential = _resolve_credential(context)
    if not isinstance(credential, OAuthCredential):
        raise exceptions.OAuthCredentialRequiredError(_credential_key(context))
    return credential
