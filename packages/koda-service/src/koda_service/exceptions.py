from __future__ import annotations


class KodaServiceError(Exception):
    """Base class for all koda-service errors."""


class ServiceError(KodaServiceError):
    """Base class for service operation errors."""


class ServiceChatError(ServiceError):
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


class ServiceNotReadyError(ServiceChatError):
    """Raised when a runtime-backed operation is attempted before the service is ready."""

    def __init__(self, *, summary: str, detail: str | None = None) -> None:
        super().__init__(summary=summary, detail=detail)


class ServiceSessionError(ServiceError):
    """Base class for session-related service errors."""


class ServiceAuthenticationError(ServiceChatError):
    """Raised when the service cannot authenticate with the active provider."""


class ServiceRateLimitError(ServiceChatError):
    """Raised when the active provider rejects a request due to rate limiting."""


class ServiceConnectionError(ServiceChatError):
    """Raised when the service cannot reach the active provider."""


class ServiceProviderError(ServiceChatError):
    """Raised for provider-side chat failures that do not need finer UI handling."""


class ServiceSessionNotFoundError(ServiceSessionError):
    """Raised when a requested session does not exist."""


class ServiceNoActiveSessionError(ServiceSessionError):
    """Raised when no active session is available."""
