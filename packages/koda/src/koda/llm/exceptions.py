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


class ModelUnavailable(LLMConfigurationError):  # noqa: N818 - reads as the condition
    """There's no model to use: one subclass per reason, for the caller to explain."""


class NoProviderConnected(ModelUnavailable):
    """No provider has a credential."""

    def __init__(self) -> None:
        super().__init__("No provider is connected")


class NoModelSelected(ModelUnavailable):
    """No model is picked."""

    def __init__(self) -> None:
        super().__init__("No model selected")


class ModelNotFound(ModelUnavailable):
    """The catalog has no such provider or model."""


class ModelNotConnected(ModelUnavailable):
    """The model exists, but none of its connections has a credential."""

    def __init__(self, provider: str, model: str) -> None:
        super().__init__(f"Model '{model}' of provider '{provider}' is not connected")
        self.provider = provider
        self.model = model


class CredentialsError(LLMConfigurationError):
    """The credentials file can't be read."""

    def __init__(self, path: Path, error: Exception) -> None:
        super().__init__(f"Can't read credentials from {path}: {error}")
        self.path = path


class LLMAPIError(LLMError):
    """The provider answered with an error. ``provider_message`` is its own explanation,
    in plain words, when it gave one."""

    def __init__(
        self,
        backend_name: str,
        error: Exception,
        *,
        message: str | None = None,
        provider_message: str | None = None,
    ) -> None:
        super().__init__(message or f"{backend_name} API error: {error}")
        self.backend_name = backend_name
        self.error = error
        self.provider_message = provider_message


class LLMConnectionError(LLMAPIError):
    """The provider couldn't be reached."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(backend_name, error, message=f"{backend_name} connection error: {error}")


class LLMRateLimitError(LLMAPIError):
    """The provider's rate limit is exceeded."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name,
            error,
            message=f"{backend_name} rate limit exceeded: {error}",
        )


class LLMAuthenticationError(LLMAPIError):
    """The provider rejected the credential."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name,
            error,
            message=f"{backend_name} authentication failed: {error}",
        )
