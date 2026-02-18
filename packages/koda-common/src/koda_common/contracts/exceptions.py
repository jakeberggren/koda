class BackendAuthenticationError(Exception):
    """Raised when backend authentication fails for the selected provider."""


class BackendSessionNotFoundError(Exception):
    """Raised when a requested session is not found."""


class BackendNoActiveSessionError(Exception):
    """Raised when no active session exists."""
