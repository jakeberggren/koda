"""Custom exceptions for the agents framework."""


class ProviderError(Exception):
    """Base exception for all provider-related errors."""


class ProviderAPIError(ProviderError):
    """API-related errors from providers.

    This includes network errors, HTTP errors, and other API communication issues.
    """


class ProviderRateLimitError(ProviderAPIError):
    """Rate limit exceeded error.

    Raised when the provider API rate limit has been exceeded.
    """


class ProviderAuthenticationError(ProviderAPIError):
    """Authentication error.

    Raised when API key is invalid or authentication fails.
    """


class ProviderValidationError(ProviderError):
    """Input validation error.

    Raised when input parameters are invalid.
    """


class ProviderResponseError(ProviderError):
    """Response parsing or validation error.

    Raised when the provider returns an invalid or unexpected response format.
    """
