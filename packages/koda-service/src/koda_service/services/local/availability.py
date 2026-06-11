from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.exceptions import LLMConfigurationError
from koda_common.settings import SecretsLoadError
from koda_common.settings.credentials import ApiKeyCredential, ProviderCredential
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

    @staticmethod
    def _connection_key(provider_id: str, connection_id: str) -> str:
        return f"{provider_id}:{connection_id}"

    def _get_credential(
        self, credential_key: str
    ) -> tuple[ProviderCredential | None, ServiceStatus | None]:
        """Read a provider connection credential or return a status error."""
        try:
            return self.settings.get_credential(credential_key), None
        except SecretsLoadError as e:
            status = ServiceStatus.from_startup_error(StartupError.from_secrets_load_error(e))
            return None, status

    def configured_provider_ids(self) -> tuple[set[str], ServiceStatus | None]:
        """Return configured provider IDs or a status error."""
        try:
            provider_ids = {
                provider.id
                for provider in self.runtime.llm_factory.list_providers()
                if any(
                    self.settings.get_credential(self._connection_key(provider.id, connection.id))
                    for connection in provider.connections
                )
            }
        except SecretsLoadError as e:
            status = ServiceStatus.from_startup_error(StartupError.from_secrets_load_error(e))
            return set(), status

        if not provider_ids:
            return set(), ServiceStatus(
                code=ServiceStatusCode.PROVIDER_SETUP_REQUIRED,
                summary="Provider setup required",
                detail="Connect provider credentials in settings to continue.",
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
                detail="The selected provider does not have credentials configured.",
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

    @staticmethod
    def _model_selection_required_status() -> ServiceStatus:
        return ServiceStatus(
            code=ServiceStatusCode.MODEL_SELECTION_REQUIRED,
            summary="Model selection required",
            detail="Select a model in settings to continue.",
        )

    @staticmethod
    def _model_unavailable_status() -> ServiceStatus:
        return ServiceStatus(
            code=ServiceStatusCode.MODEL_UNAVAILABLE,
            summary="Selected model unavailable",
            detail="Choose a different model in settings.",
        )

    @staticmethod
    def _credential_status(
        credential: ProviderCredential | None,
        *,
        provider_id: str,
        connection_id: str,
    ) -> ServiceStatus | None:
        if credential is None:
            return ServiceStatus(
                code=ServiceStatusCode.API_KEY_NOT_CONFIGURED,
                summary=f"{provider_id} {connection_id} credentials not configured",
            )
        if isinstance(credential, ApiKeyCredential) and not credential.value.strip():
            return ServiceStatus(
                code=ServiceStatusCode.API_KEY_EMPTY,
                summary=f"{provider_id} {connection_id} API key cannot be empty",
            )
        return None

    def credentials_status(self) -> ServiceStatus | None:
        """Validate credentials for the selected provider/model route."""
        provider = self.settings.provider
        model = self.settings.model
        if provider is None or model is None:
            return self._model_selection_required_status()

        try:
            route = self.runtime.llm_factory.resolve_route_for_settings(self.settings)
        except LLMConfigurationError:
            return self._model_unavailable_status()

        credential_key = self._connection_key(route.provider_id, route.connection_id)
        credential, status = self._get_credential(credential_key)
        if status is not None:
            return status
        return self._credential_status(
            credential,
            provider_id=route.provider_id,
            connection_id=route.connection_id,
        )

    def tools_status(self) -> ServiceStatus | None:
        """Validate sync runtime dependencies that do not require LLM construction."""
        if self.runtime.agent is not None:
            return None
        try:
            self.runtime.create_tools()
        except StartupConfigurationError as e:
            return ServiceStatus.from_startup_error(e)
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

        status = self.tools_status()
        if status is not None:
            return status

        return ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")
