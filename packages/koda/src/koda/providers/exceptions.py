class ProviderError(Exception):
    """Base exception for all provider-related errors."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class ProviderAPIError(ProviderError):
    """API-related errors from providers."""

    def __init__(self, provider_name: str, error: Exception) -> None:
        super().__init__(f"{provider_name} API error: {error}")
        self.provider_name = provider_name
        self.error = error


class ProviderConnectionError(ProviderAPIError):
    """Connection error from provider."""

    def __init__(self, provider_name: str, error: Exception) -> None:
        super().__init__(provider_name, error)
        self.message = f"{provider_name} connection error: {error}"


class ProviderRateLimitError(ProviderAPIError):
    """Rate limit exceeded error."""

    def __init__(self, provider_name: str, error: Exception) -> None:
        super().__init__(provider_name, error)
        self.message = f"{provider_name} rate limit exceeded: {error}"


class ProviderAuthenticationError(ProviderAPIError):
    """Authentication error."""

    def __init__(self, provider_name: str, error: Exception) -> None:
        super().__init__(provider_name, error)
        self.message = f"{provider_name} authentication failed: {error}"


class ProviderValidationError(ProviderError):
    """Input validation error."""


class EmptyMessageError(ProviderValidationError):
    """Message cannot be empty."""

    def __init__(self) -> None:
        super().__init__("Message cannot be empty")


class EmptyApiKeyError(ProviderValidationError):
    """API key cannot be empty."""

    def __init__(self, provider_name: str = "Provider") -> None:
        super().__init__(f"{provider_name} API key cannot be empty")


class ApiKeyNotConfiguredError(ProviderValidationError):
    """API key is not configured."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"{provider_name} API key not configured")


class EmptyMessagesListError(ProviderValidationError):
    """Messages list cannot be empty."""

    def __init__(self) -> None:
        super().__init__("Messages list cannot be empty")


class ProviderConfigurationError(ProviderError):
    """Provider configuration or registry error."""


class ProviderAlreadyRegisteredError(ProviderConfigurationError):
    """Provider is already registered."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Provider '{provider_name}' is already registered")
        self.provider_name = provider_name


class ProviderNotSupportedError(ProviderConfigurationError):
    """Provider is not supported."""

    def __init__(self, provider_name: str, supported: str) -> None:
        super().__init__(
            f"Provider '{provider_name}' is not supported. Supported providers: {supported}"
        )
        self.provider_name = provider_name
        self.supported = supported


class ProviderNameEmptyError(ProviderConfigurationError):
    """Provider name cannot be empty."""

    def __init__(self) -> None:
        super().__init__("Provider name cannot be empty")


class UnknownMessageTypeError(ProviderError):
    """Unknown message type encountered."""

    def __init__(self, message_type: type) -> None:
        super().__init__(f"Unknown message type: {message_type}")
        self.message_type = message_type
