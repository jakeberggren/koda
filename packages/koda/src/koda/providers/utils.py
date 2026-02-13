from __future__ import annotations

from typing import Literal

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from koda.providers import exceptions
from koda_common.logging import get_logger

logger = get_logger(__name__)


def handle_provider_exceptions(
    e: Exception,
    *,
    provider: Literal["BergetAI", "OpenAI", "Anthropic"],
) -> None:
    if isinstance(e, RateLimitError):
        logger.error("provider_rate_limit_error", provider=provider)
        raise exceptions.ProviderRateLimitError(provider, e) from e
    if isinstance(e, AuthenticationError):
        logger.error("provider_authentication_error", provider=provider)
        raise exceptions.ProviderAuthenticationError(provider, e) from e
    if isinstance(e, APIConnectionError | APITimeoutError):
        logger.error("provider_connection_error", provider=provider, error=repr(e))
        raise exceptions.ProviderConnectionError(provider, e) from e
    if isinstance(e, APIError):
        logger.error("provider_api_error", provider=provider, error=repr(e))
        raise exceptions.ProviderAPIError(provider, e) from e
    logger.error("provider_unknown_error", provider=provider, error=repr(e))
    raise exceptions.ProviderAPIError(provider, e) from e
