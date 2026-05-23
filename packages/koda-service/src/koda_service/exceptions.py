from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)
from koda_common.settings import (
    SecretsDecodeError,
    SecretsLoadError,
    SecretsPermissionError,
    SettingsDecodeError,
    SettingsLoadError,
    SettingsPermissionError,
    SettingsStructureError,
    SettingsUnknownKeysError,
    SettingsValidationError,
)

if TYPE_CHECKING:
    import json

    from pydantic import ValidationError

    from koda.tools.exceptions import ToolError


class KodaServiceError(Exception):
    """Base class for all koda-service errors."""


class ServiceChatError(KodaServiceError):
    """Base class for user-facing chat failures surfaced by the service."""

    def __init__(
        self,
        *,
        summary: str,
        detail: str | None = None,
        message: str | None = None,
    ) -> None:
        super().__init__(summary)
        self.summary = summary
        self.detail = detail
        self.message = message or detail or summary

    @classmethod
    def from_llm_error(cls, error: LLMError) -> ServiceChatError:
        """Convert a core LLM error into a user-facing service chat error."""
        if isinstance(error, LLMAuthenticationError):
            return ServiceAuthenticationError(
                summary="Authentication failed.",
                detail=f"{error.message}\n\nPlease check your API key and try again.",
                message=error.message,
            )
        if isinstance(error, LLMRateLimitError):
            return ServiceRateLimitError(
                summary="Rate limit exceeded.",
                detail=f"{error.message}\n\nPlease check your plan and billing details.",
                message=error.message,
            )
        if isinstance(error, LLMConnectionError):
            return ServiceConnectionError(
                summary="Connection error.",
                detail=f"{error.message}\n\nPlease check your internet connection and try again.",
                message=error.message,
            )
        if isinstance(error, LLMAPIError):
            return ServiceProviderError(
                summary="Provider error.",
                detail=error.message,
                message=error.message,
            )

        message = str(error)
        return ServiceProviderError(
            summary="Request failed.",
            detail=message,
            message=message,
        )

    @classmethod
    def from_tool_error(cls, error: ToolError) -> ServiceChatError:
        """Convert a core tool error into a user-facing service chat error."""
        message = str(error)
        return ServiceToolError(
            summary="Tool execution failed.",
            detail=message,
            message=message,
        )


class ServiceNotReadyError(ServiceChatError):
    """Raised when a runtime-backed operation is attempted before the service is ready."""

    def __init__(self, *, summary: str, detail: str | None = None) -> None:
        super().__init__(summary=summary, detail=detail)


class ServiceSessionError(KodaServiceError):
    """Base class for session-related service errors."""


class ServiceAuthenticationError(ServiceChatError):
    """Raised when the service cannot authenticate with the active provider."""


class ServiceRateLimitError(ServiceChatError):
    """Raised when the active provider rejects a request due to rate limiting."""


class ServiceConnectionError(ServiceChatError):
    """Raised when the service cannot reach the active provider."""


class ServiceProviderError(ServiceChatError):
    """Raised for provider-side chat failures that do not need finer UI handling."""


class ServiceToolError(ServiceChatError):
    """Raised for local tool or agent tool-loop failures."""


class ServiceSessionNotFoundError(ServiceSessionError):
    """Raised when a requested session does not exist."""


class StartupError(KodaServiceError):
    """Base class for user-fixable startup failures."""

    def __init__(self, summary: str, *, details: tuple[str, ...] = ()) -> None:
        super().__init__(summary)
        self.summary = summary
        self.details = details

    def __str__(self) -> str:
        if not self.details:
            return self.summary
        details = "\n".join(f"- {detail}" for detail in self.details)
        return f"{self.summary}\n{details}"

    @classmethod
    def from_settings_load_error(cls, error: SettingsLoadError) -> StartupError:
        """Convert settings storage errors into user-fixable startup errors."""
        if isinstance(error, SettingsValidationError):
            return StartupConfigurationError.from_validation_error(error.error)
        if isinstance(error, (SettingsUnknownKeysError, SettingsStructureError)):
            return StartupConfigurationError.from_runtime_error(error)
        if isinstance(error, SettingsPermissionError):
            return StartupEnvironmentError.from_permission_error(error.error)
        if isinstance(error, SettingsDecodeError):
            return StartupConfigurationError.from_json_decode_error(
                path=str(error.path),
                error=error.error,
            )
        raise TypeError

    @classmethod
    def from_secrets_load_error(cls, error: SecretsLoadError) -> StartupError:
        """Convert secrets storage errors into user-fixable startup errors."""
        if isinstance(error, SecretsPermissionError):
            return StartupEnvironmentError.from_permission_error(error.error)
        if isinstance(error, SecretsDecodeError):
            return StartupConfigurationError.from_json_decode_error(
                path=str(error.path),
                error=error.error,
            )
        raise TypeError


class StartupConfigurationError(StartupError):
    """Raised when startup fails due to invalid or incomplete configuration."""

    @classmethod
    def from_json_decode_error(
        cls,
        *,
        path: str,
        error: json.JSONDecodeError,
    ) -> StartupConfigurationError:
        return cls(
            f"Settings file is not valid JSON: {path}",
            details=(f"{error.msg} at line {error.lineno}, column {error.colno}",),
        )

    @classmethod
    def from_validation_error(cls, error: ValidationError) -> StartupConfigurationError:
        details = tuple(
            f"{'.'.join(str(part) for part in issue['loc']) or '<root>'}: {issue['msg']}"
            for issue in error.errors(include_url=False)
        )
        return cls("Invalid configuration", details=details)

    @classmethod
    def from_runtime_error(cls, error: Exception) -> StartupConfigurationError:
        return cls(str(error))


class StartupEnvironmentError(StartupError):
    """Raised when startup fails due to local environment or filesystem issues."""

    @classmethod
    def from_permission_error(cls, error: PermissionError) -> StartupEnvironmentError:
        return cls(
            "Koda could not access required local files",
            details=(str(error),),
        )
