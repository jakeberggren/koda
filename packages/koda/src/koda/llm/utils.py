from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, NoReturn

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from koda.llm import exceptions
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai import AsyncOpenAI

    from koda_common.settings import SettingsManager

logger = get_logger(__name__)


def resolve_openai_client(settings: SettingsManager) -> Callable[..., AsyncOpenAI]:
    if not settings.langfuse_tracing_enabled:
        return importlib.import_module("openai").AsyncOpenAI
    try:
        return importlib.import_module("langfuse.openai").AsyncOpenAI
    except ModuleNotFoundError:
        logger.warning("langfuse_client_unavailable_falling_back_to_openai")
        return importlib.import_module("openai").AsyncOpenAI


def raise_llm_error_from_openai(
    error: OpenAIError,
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
