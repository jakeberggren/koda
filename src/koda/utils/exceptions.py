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


class ToolError(Exception):
    """Base exception for all tool-related errors."""


class ToolValidationError(ToolError):
    """Tool argument validation error."""


class ToolExecutionError(ToolError):
    """Tool execution error."""


class MaxIterationsExceededError(ToolError):
    """Maximum tool call iterations exceeded."""
