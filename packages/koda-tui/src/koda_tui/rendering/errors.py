"""Errors: what the chat says about an error. Always our words, never the error's own,
except a provider's explanation of what it refused."""

from __future__ import annotations

from dataclasses import dataclass

from koda.llm import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)
from koda.tools import ToolError
from koda_tui import strings


@dataclass(frozen=True, slots=True)
class ErrorText:
    """What went wrong, what to do about it when there is something to do, and the
    provider's own words when it gave some."""

    summary: str
    hint: str | None = None
    detail: str | None = None


def describe(error: Exception) -> ErrorText:  # noqa: C901, PLR0911 - one case per kind of error
    """What to tell the user about ``error``."""
    errors = strings.Screen.Chat.Errors
    match error:
        case LLMAuthenticationError():
            return ErrorText(errors.AUTHENTICATION, errors.AUTHENTICATION_FIX)
        case LLMRateLimitError():
            return ErrorText(errors.RATE_LIMIT, errors.RATE_LIMIT_FIX)
        case LLMConnectionError():
            return ErrorText(errors.CONNECTION, errors.CONNECTION_FIX)
        case LLMAPIError(provider_message=detail):
            return ErrorText(errors.PROVIDER, detail=detail)
        case LLMConfigurationError():
            return ErrorText(errors.NOT_READY)
        case LLMError():
            return ErrorText(errors.REQUEST)
        case ToolError():
            return ErrorText(errors.TOOL)
        case _:
            return ErrorText(errors.UNEXPECTED, errors.UNEXPECTED_FIX)
