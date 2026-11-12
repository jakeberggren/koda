from __future__ import annotations

from koda.llm.apis import LLMApiContext
from koda.llm.auth.protocols import OAuthLoginCallbacks
from koda.llm.auth.registry import ProviderAuthRegistry
from koda.llm.catalog import Catalog, CatalogWarning
from koda.llm.credentials import (
    ApiKeyCredential,
    Credentials,
    JsonCredentialStore,
    OAuthCredential,
    ProviderCredential,
)
from koda.llm.exceptions import (
    CredentialsError,
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)
from koda.llm.models import (
    AuthMethod,
    Connection,
    Model,
    Provider,
    ThinkingOption,
    ThinkingOptionId,
    resolve_thinking_mode,
)
from koda.llm.protocols import LLM
from koda.llm.types import (
    LLMEvent,
    LLMRequest,
    LLMRequestOptions,
    LLMRequestOptionsError,
    LLMResponse,
    ThinkingMode,
)


async def connect(
    model: Model,
    credentials: Credentials,
    *,
    tracing: bool = False,
    auth_registry: ProviderAuthRegistry | None = None,
) -> LLM:
    """An LLM for ``model``, over the connection ``credentials`` can use.

    With ``tracing``, OpenAI-compatible clients are traced to Langfuse.
    """
    connection = model.connection(credentials)
    return await connection.api.from_context(
        LLMApiContext(
            model=model,
            connection=connection,
            credentials=credentials,
            auth_registry=auth_registry or ProviderAuthRegistry.default(),
            tracing=tracing,
        )
    )


async def login(connection: Connection, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
    """Log in to the OAuth ``connection`` through the browser; ``callbacks`` open the URL
    and ask for anything the login needs."""
    return await ProviderAuthRegistry.default().get(connection.credential_key).login(callbacks)


__all__ = [
    "LLM",
    "ApiKeyCredential",
    "AuthMethod",
    "Catalog",
    "CatalogWarning",
    "Connection",
    "Credentials",
    "CredentialsError",
    "JsonCredentialStore",
    "LLMAPIError",
    "LLMAuthenticationError",
    "LLMConfigurationError",
    "LLMConnectionError",
    "LLMError",
    "LLMEvent",
    "LLMRateLimitError",
    "LLMRequest",
    "LLMRequestOptions",
    "LLMRequestOptionsError",
    "LLMResponse",
    "Model",
    "OAuthCredential",
    "OAuthLoginCallbacks",
    "Provider",
    "ProviderCredential",
    "ThinkingMode",
    "ThinkingOption",
    "ThinkingOptionId",
    "connect",
    "login",
    "resolve_thinking_mode",
]
