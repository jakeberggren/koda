from __future__ import annotations

from koda.llm.apis import LLMApiContext
from koda.llm.auth.registry import ProviderAuthRegistry
from koda.llm.catalog import Catalog, CatalogWarning
from koda.llm.credentials import (
    ApiKeyCredential,
    Credentials,
    JsonCredentialStore,
    OAuthCredential,
    ProviderCredential,
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


__all__ = [
    "LLM",
    "ApiKeyCredential",
    "AuthMethod",
    "Catalog",
    "CatalogWarning",
    "Connection",
    "Credentials",
    "JsonCredentialStore",
    "LLMEvent",
    "LLMRequest",
    "LLMRequestOptions",
    "LLMRequestOptionsError",
    "LLMResponse",
    "Model",
    "OAuthCredential",
    "Provider",
    "ProviderCredential",
    "ThinkingMode",
    "ThinkingOption",
    "ThinkingOptionId",
    "connect",
    "resolve_thinking_mode",
]
