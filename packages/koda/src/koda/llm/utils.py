from __future__ import annotations

from typing import NoReturn

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from koda.llm import exceptions
from koda_common.logging import get_logger

logger = get_logger(__name__)


def raise_openai_error(
    error: Exception,
    *,
    backend: str,
) -> NoReturn:
    if isinstance(error, RateLimitError):
        logger.error("llm_rate_limit_error", backend=backend)
        raise exceptions.LLMRateLimitError(backend, error) from error
    if isinstance(error, AuthenticationError):
        logger.error("llm_authentication_error", backend=backend)
        raise exceptions.LLMAuthenticationError(backend, error) from error
    if isinstance(error, APIConnectionError | APITimeoutError):
        logger.error("llm_connection_error", backend=backend, error=repr(error))
        raise exceptions.LLMConnectionError(backend, error) from error
    if isinstance(error, APIError):
        logger.error("llm_api_error", backend=backend, error=repr(error))
        raise exceptions.LLMAPIError(backend, error) from error
    logger.error("llm_unknown_error", backend=backend, error=repr(error))
    raise exceptions.LLMAPIError(backend, error) from error
