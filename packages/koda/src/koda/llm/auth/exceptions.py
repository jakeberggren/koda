class OAuthCallbackError(Exception):
    """Base error for local OAuth callback failures."""


class OAuthCallbackTimeoutError(OAuthCallbackError):
    """Raised when the OAuth redirect does not arrive before the timeout."""

    def __init__(self) -> None:
        super().__init__("Timed out waiting for OAuth callback")


class OAuthCallbackCancelledError(OAuthCallbackError):
    """Raised when the OAuth callback listener is cancelled."""

    def __init__(self) -> None:
        super().__init__("OAuth callback listener was cancelled")


class OAuthCallbackStateError(OAuthCallbackError):
    """Raised when the OAuth callback state does not match the login flow."""

    def __init__(self) -> None:
        super().__init__("OAuth state mismatch")


class OAuthCallbackCodeMissingError(OAuthCallbackError):
    """Raised when the OAuth callback does not include an authorization code."""

    def __init__(self) -> None:
        super().__init__("Missing authorization code")


class OAuthCallbackRedirectError(OAuthCallbackError):
    """Raised when a pasted callback URL does not match the expected redirect."""

    def __init__(self) -> None:
        super().__init__("OAuth callback URL does not match the expected redirect")


class AuthNameEmptyError(Exception):
    """Raised when an auth provider id is empty."""

    def __init__(self) -> None:
        super().__init__("Auth provider id cannot be empty")


class AuthAlreadyRegisteredError(Exception):
    """Raised when an auth provider id is registered more than once."""

    def __init__(self, auth_id: str) -> None:
        super().__init__(f"Auth provider '{auth_id}' is already registered")
        self.auth_id = auth_id


class AuthNotSupportedError(Exception):
    """Raised when an auth provider id is not registered."""

    def __init__(self, auth_id: str) -> None:
        super().__init__(f"Auth provider '{auth_id}' is not supported")
        self.auth_id = auth_id


class OpenAICodexAuthError(Exception):
    """Base error for OpenAI Codex OAuth failures."""


class OpenAICodexAccountMissingError(OpenAICodexAuthError):
    """Raised when the OpenAI access token does not contain a ChatGPT account id."""

    def __init__(self) -> None:
        super().__init__("OpenAI Codex access token is missing ChatGPT account id")


class OpenAICodexTokenError(OpenAICodexAuthError):
    """Raised when OpenAI Codex token exchange or refresh fails."""

    def __init__(self, operation: str, detail: str) -> None:
        super().__init__(f"OpenAI Codex token {operation} failed: {detail}")
