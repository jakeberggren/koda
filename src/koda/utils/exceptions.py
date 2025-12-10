class ProviderError(Exception):
    """Base exception for all provider-related errors."""


class ProviderAPIError(ProviderError):
    """API-related errors from providers."""


class ProviderRateLimitError(ProviderAPIError):
    """Rate limit exceeded error."""


class ProviderAuthenticationError(ProviderAPIError):
    """Authentication error."""


class ProviderValidationError(ProviderError):
    """Input validation error."""


class ProviderResponseError(ProviderError):
    """Response parsing or validation error."""
