"""Tests for what the chat says about an error."""

from __future__ import annotations

import pytest

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
from koda_tui.rendering.errors import ErrorText, describe

ERRORS = strings.Screen.Chat.Errors
CAUSE = RuntimeError("raw details")


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (
            LLMAuthenticationError("openai", CAUSE),
            ErrorText(ERRORS.AUTHENTICATION, ERRORS.AUTHENTICATION_FIX),
        ),
        (LLMRateLimitError("openai", CAUSE), ErrorText(ERRORS.RATE_LIMIT, ERRORS.RATE_LIMIT_FIX)),
        (
            LLMConnectionError("openai", CAUSE),
            ErrorText(ERRORS.CONNECTION, ERRORS.CONNECTION_FIX),
        ),
        (
            LLMAPIError("codex", CAUSE, provider_message="Model not supported."),
            ErrorText(ERRORS.PROVIDER, detail="Model not supported."),
        ),
        (LLMAPIError("openai", CAUSE), ErrorText(ERRORS.PROVIDER)),
        (LLMConfigurationError("No model selected"), ErrorText(ERRORS.NOT_READY)),
        (LLMError("Tool call arguments must decode to a JSON object"), ErrorText(ERRORS.REQUEST)),
        (ToolError("boom"), ErrorText(ERRORS.TOOL)),
        (KeyError("max"), ErrorText(ERRORS.UNEXPECTED, ERRORS.UNEXPECTED_FIX)),
    ],
)
def test_each_error_is_told_in_our_words(error: Exception, text: ErrorText) -> None:
    assert describe(error) == text
