"""What can go wrong with an LLM: one type per way a caller reacts to it."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class LLMError(Exception):
    """Anything that goes wrong in ``koda.llm``."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class LLMConfigurationError(LLMError):
    """Koda isn't set up to use the model: no credential, an unknown model, a provider
    that isn't connected, or a catalog entry missing what the API needs."""


class CredentialsError(LLMConfigurationError):
    """The credentials file can't be read."""

    def __init__(self, path: Path, error: Exception) -> None:
        super().__init__(f"Can't read credentials from {path}: {error}")
        self.path = path


class LLMAPIError(LLMError):
    """The provider answered with an error."""

    def __init__(self, backend_name: str, error: Exception, *, message: str | None = None) -> None:
        super().__init__(message or f"{backend_name} API error: {error}")
        self.backend_name = backend_name
        self.error = error


class LLMConnectionError(LLMAPIError):
    """The provider couldn't be reached."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(backend_name, error, message=f"{backend_name} connection error: {error}")


class LLMRateLimitError(LLMAPIError):
    """The provider's rate limit is exceeded."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name, error, message=f"{backend_name} rate limit exceeded: {error}"
        )


class LLMAuthenticationError(LLMAPIError):
    """The provider rejected the credential."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name, error, message=f"{backend_name} authentication failed: {error}"
        )
