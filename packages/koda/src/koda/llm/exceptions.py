class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class LLMAPIError(LLMError):
    """API-related errors from LLM backends."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(f"{backend_name} API error: {error}")
        self.backend_name = backend_name
        self.error = error


class LLMConnectionError(LLMAPIError):
    """Connection errors from the LLM backend."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(backend_name, error)
        self.message = f"{backend_name} connection error: {error}"


class LLMRateLimitError(LLMAPIError):
    """Rate limit exceeded for the LLM backend."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(backend_name, error)
        self.message = f"{backend_name} rate limit exceeded: {error}"


class LLMAuthenticationError(LLMAPIError):
    """Authentication error from the LLM backend."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(backend_name, error)
        self.message = f"{backend_name} authentication failed: {error}"


class LLMValidationError(LLMError):
    """Input validation error."""


class InvalidToolCallArgumentsError(LLMValidationError):
    """Tool call arguments must decode to a JSON object."""

    def __init__(self) -> None:
        super().__init__("Tool call arguments must decode to a JSON object")


class EmptyMessageError(LLMValidationError):
    """Message cannot be empty."""

    def __init__(self) -> None:
        super().__init__("Message cannot be empty")


class EmptyApiKeyError(LLMValidationError):
    """API key cannot be empty."""

    def __init__(self, backend_name: str = "LLM backend") -> None:
        super().__init__(f"{backend_name} API key cannot be empty")


class ApiKeyNotConfiguredError(LLMValidationError):
    """API key is not configured."""

    def __init__(self, backend_name: str) -> None:
        super().__init__(f"{backend_name} API key not configured")


class EmptyMessagesListError(LLMValidationError):
    """Messages list cannot be empty."""

    def __init__(self) -> None:
        super().__init__("Messages list cannot be empty")


class UnknownMessageTypeError(LLMError):
    """Unknown message type encountered."""

    def __init__(self, message_type: type) -> None:
        super().__init__(f"Unknown message type: {message_type}")
        self.message_type = message_type


class StructuredOutputNotSupportedError(LLMError):
    """Structured outputs are not supported by this backend implementation."""
