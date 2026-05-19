from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.exceptions import LLMConfigurationError
from koda_common.settings import SecretsLoadError
from koda_service.exceptions import (
    StartupConfigurationError,
    StartupEnvironmentError,
    StartupError,
)
from koda_service.models import ServiceStatus, ServiceStatusCode

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager
    from koda_service.services.local.runtime import LocalRuntime


class LocalAvailability:
    """Evaluates whether the local runtime can currently execute chat."""

    def __init__(self, *, settings: SettingsManager, runtime: LocalRuntime) -> None:
        self.settings = settings
        self.runtime = runtime

    def _get_api_key(self, provider: str) -> tuple[str | None, ServiceStatus | None]:
        """Read the provider API key or return a status error."""
        try:
            return self.settings.get_api_key(provider), None
        except SecretsLoadError as e:
            status = ServiceStatus.from_startup_error(StartupError.from_secrets_load_error(e))
            return None, status

    def configured_provider_ids(self) -> tuple[set[str], ServiceStatus | None]:
        """Return configured provider IDs or a status error."""
        try:
            provider_ids = {
                provider.id
                for provider in self.runtime.llm_factory.list_providers()
                if self.settings.get_api_key(provider.id)
            }
        except SecretsLoadError as e:
            status = ServiceStatus.from_startup_error(StartupError.from_secrets_load_error(e))
            return set(), status

        if not provider_ids:
            return set(), ServiceStatus(
                code=ServiceStatusCode.PROVIDER_SETUP_REQUIRED,
                summary="Provider setup required",
                detail="Connect a provider API key in settings to continue.",
            )

        return provider_ids, None

    def selection_status(self, configured_provider_ids: set[str]) -> ServiceStatus | None:
        """Validate the selected provider and model."""
        provider = self.settings.provider
        model = self.settings.model
        if provider is None or model is None:
            return ServiceStatus(
                code=ServiceStatusCode.MODEL_SELECTION_REQUIRED,
                summary="Model selection required",
                detail="Select a model in settings to continue.",
            )

        if provider not in configured_provider_ids:
            return ServiceStatus(
                code=ServiceStatusCode.PROVIDER_NOT_CONNECTED,
                summary=f"Connect {provider} to continue",
                detail="The selected provider does not have an API key configured.",
            )

        try:
            self.runtime.llm_factory.validate_selection(provider, model)
        except LLMConfigurationError:
            return ServiceStatus(
                code=ServiceStatusCode.MODEL_UNAVAILABLE,
                summary="Selected model unavailable",
                detail="Choose a different model in settings.",
            )

        return None

    def credentials_status(self) -> ServiceStatus | None:
        """Validate credentials for the selected provider."""
        provider = self.settings.provider
        if provider is None:
            return ServiceStatus(
                code=ServiceStatusCode.MODEL_SELECTION_REQUIRED,
                summary="Model selection required",
                detail="Select a model in settings to continue.",
            )

        api_key, status = self._get_api_key(provider)
        if status is not None:
            return status
        if api_key is None:
            return ServiceStatus(
                code=ServiceStatusCode.API_KEY_NOT_CONFIGURED,
                summary=f"{provider} API key not configured",
            )
        if not api_key.strip():
            return ServiceStatus(
                code=ServiceStatusCode.API_KEY_EMPTY,
                summary=f"{provider} API key cannot be empty",
            )
        return None

    def agent_status(self) -> ServiceStatus | None:
        """Build the cached agent if needed and return any blocking status."""
        if self.runtime.agent is not None:
            return None
        try:
            self.runtime.get_agent()
        except StartupConfigurationError as e:
            return ServiceStatus.from_startup_error(e)
        except SecretsLoadError as e:
            return ServiceStatus.from_startup_error(StartupError.from_secrets_load_error(e))
        except PermissionError as e:
            startup_error = StartupEnvironmentError.from_permission_error(e)
            return ServiceStatus.from_startup_error(startup_error)

        return None

    def status(self) -> ServiceStatus:
        """Return whether the local runtime is currently available for chat."""
        configured_provider_ids, status = self.configured_provider_ids()
        if status is not None:
            return status

        status = self.selection_status(configured_provider_ids)
        if status is not None:
            return status

        status = self.credentials_status()
        if status is not None:
            return status

        status = self.agent_status()
        if status is not None:
            return status

        return ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")
