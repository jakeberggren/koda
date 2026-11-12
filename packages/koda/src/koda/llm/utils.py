from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING, Any, NoReturn

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)
from structlog import get_logger

from koda.llm import exceptions

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai import AsyncOpenAI

logger = get_logger(__name__)


def resolve_openai_client(*, tracing: bool) -> Callable[..., AsyncOpenAI]:
    if not tracing:
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


def tool_arguments(value: object) -> dict[str, Any]:
    """``value`` as tool call arguments, which must be a JSON object."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise exceptions.LLMError("Tool call arguments must decode to a JSON object")
    return value


def parse_tool_arguments(raw: str) -> dict[str, Any]:
    """The tool call arguments in the JSON text ``raw``."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise exceptions.LLMError("Tool call arguments must decode to a JSON object") from error
    return tool_arguments(value)
