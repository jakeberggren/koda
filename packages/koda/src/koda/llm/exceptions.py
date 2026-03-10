class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class LLMAPIError(LLMError):
    """API-related errors from LLM backends."""

    def __init__(
        self,
        backend_name: str,
        error: Exception,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(message or f"{backend_name} API error: {error}")
        self.backend_name = backend_name
        self.error = error


class LLMConnectionError(LLMAPIError):
    """Connection errors from the LLM backend."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name,
            error,
            message=f"{backend_name} connection error: {error}",
        )


class LLMRateLimitError(LLMAPIError):
    """Rate limit exceeded for the LLM backend."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name,
            error,
            message=f"{backend_name} rate limit exceeded: {error}",
        )


class LLMAuthenticationError(LLMAPIError):
    """Authentication error from the LLM backend."""

    def __init__(self, backend_name: str, error: Exception) -> None:
        super().__init__(
            backend_name,
            error,
            message=f"{backend_name} authentication failed: {error}",
        )


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


class ModelConfigurationError(LLMError):
    """LLM model configuration or registry error."""


class ProviderConfigurationError(LLMError):
    """LLM provider configuration or registry error."""


class ProviderNameEmptyError(ProviderConfigurationError):
    def __init__(self) -> None:
        super().__init__("Provider name cannot be empty")


class ProviderAlreadyRegisteredError(ProviderConfigurationError):
    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Provider '{provider_name}' is already registered")
        self.provider_name = provider_name


class ProviderNotSupportedError(ProviderConfigurationError):
    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Provider '{provider_name}' is not supported")
        self.provider_name = provider_name


class ModelAlreadyRegisteredError(ModelConfigurationError):
    def __init__(self, model_name: str, provider_name: str) -> None:
        super().__init__(f"Model '{model_name}' for provider {provider_name} is already registered")
        self.model_name = model_name
        self.provider_name = provider_name


class ModelNotSupportedError(ModelConfigurationError):
    def __init__(self, model_id: str, provider_name: str) -> None:
        super().__init__(f"Model '{model_id}' for provider {provider_name} is not supported")
        self.model_id = model_id
        self.provider_name = provider_name
