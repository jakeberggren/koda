class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class LLMConfigurationError(LLMError):
    """Configuration or setup errors for LLM integrations."""


class LLMRuntimeError(LLMError):
    """Errors that happen while talking to an LLM backend."""


class LLMAPIError(LLMRuntimeError):
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


class EmptyApiKeyError(LLMConfigurationError):
    """API key cannot be empty."""

    def __init__(self, credential_key: str) -> None:
        super().__init__(f"{credential_key} API key cannot be empty")


class ProviderCredentialNotConfiguredError(LLMConfigurationError):
    """Provider credential is not configured."""

    def __init__(self, credential_key: str) -> None:
        super().__init__(f"{credential_key} credential not configured")


class ApiKeyCredentialRequiredError(LLMConfigurationError):
    """Provider is configured with a non-API-key credential."""

    def __init__(self, backend_name: str) -> None:
        super().__init__(f"{backend_name} requires an API key credential")


class OAuthCredentialRequiredError(LLMConfigurationError):
    """Provider is configured with a non-OAuth credential."""

    def __init__(self, backend_name: str) -> None:
        super().__init__(f"{backend_name} requires an OAuth credential")


class OAuthAccountIdMissingError(LLMConfigurationError):
    """OAuth credential must include an account id."""

    def __init__(self, backend_name: str) -> None:
        super().__init__(f"{backend_name} OAuth credential must include an account id")


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


class ModelConfigurationError(LLMConfigurationError):
    """LLM model configuration or registry error."""


class ProviderConfigurationError(LLMConfigurationError):
    """LLM provider configuration or registry error."""


class ProviderNotSupportedError(ProviderConfigurationError):
    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Provider '{provider_name}' is not supported")
        self.provider_name = provider_name


class ProviderNotConnectedError(ProviderConfigurationError):
    """No connection to the provider has a credential."""

    def __init__(self, provider_name: str) -> None:
        super().__init__(f"Provider '{provider_name}' is not connected")
        self.provider_name = provider_name


class ModelNotSupportedError(ModelConfigurationError):
    def __init__(self, model_id: str, provider_name: str) -> None:
        super().__init__(f"Model '{model_id}' for provider {provider_name} is not supported")
        self.model_id = model_id
        self.provider_name = provider_name


class ModelSelectionMissingError(ModelConfigurationError):
    def __init__(self) -> None:
        super().__init__("Model selection is required")


class ModelMaxOutputTokensMissingError(ModelConfigurationError):
    def __init__(self, model_id: str, provider_name: str) -> None:
        super().__init__(
            f"Model '{model_id}' for provider {provider_name} must define max_output_tokens"
        )
        self.model_id = model_id
        self.provider_name = provider_name


class ThinkingBudgetTokensNotConfiguredError(LLMConfigurationError):
    """thinking='enabled' requires budget_tokens to be configured for this model."""

    def __init__(self) -> None:
        super().__init__(
            "thinking='enabled' requires budget_tokens to be configured for this model"
        )


class ModelThinkingModeNotConfiguredError(ModelConfigurationError):
    def __init__(self, model_id: str, provider_name: str, thinking_mode: str) -> None:
        super().__init__(
            f"Model '{model_id}' for provider {provider_name} references unknown thinking mode "
            f"'{thinking_mode}'"
        )
        self.model_id = model_id
        self.provider_name = provider_name
        self.thinking_mode = thinking_mode
