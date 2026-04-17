from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.llm import exceptions as llm_exceptions
from koda.sessions import JsonSessionStore, SessionManager, SessionNotFoundError
from koda.tools import exceptions as tool_exceptions
from koda_common.settings import SecretsLoadError, SettingsManager
from koda_service.exceptions import (
    ServiceAuthenticationError,
    ServiceChatError,
    ServiceConnectionError,
    ServiceNotReadyError,
    ServiceProviderError,
    ServiceRateLimitError,
    ServiceSessionNotFoundError,
    StartupConfigurationError,
    StartupEnvironmentError,
    StartupError,
    startup_error_from_settings_error,
)
from koda_service.mappers import (
    map_llm_event_to_stream_event,
    map_messages_to_contract_messages,
    map_model_definition_to_contract_model_definition,
    map_provider_definition_to_contract_provider_definition,
    map_session_to_session_info,
)
from koda_service.protocols import KodaService
from koda_service.services.in_process.agent import InProcessAgentConfig, build_registries
from koda_service.types import (
    Message,
    ModelDefinition,
    ProviderDefinition,
    StreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path
    from uuid import UUID

    from koda.agents import Agent
    from koda.sessions.store import SessionStore
    from koda.telemetry import Telemetry
    from koda_service.types import SessionInfo


def _not_ready(*, summary: str, detail: str | None = None) -> ServiceStatus:
    """Build a not-ready service status."""
    return ServiceStatus(is_ready=False, summary=summary, detail=detail)


def _startup_error_status(error: StartupError) -> ServiceStatus:
    detail = "\n".join(error.details) if error.details else None
    return _not_ready(summary=error.summary, detail=detail)


def _api_key_error_status(error: SecretsLoadError) -> ServiceStatus:
    """Map API-key backend failures to service status."""
    return _startup_error_status(startup_error_from_settings_error(error))


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceStatus:
    is_ready: bool = False
    summary: str = ""
    detail: str | None = None


class InProcessKodaService(KodaService[StreamEvent, ProviderDefinition, ModelDefinition, Message]):
    def __init__(
        self,
        *,
        settings: SettingsManager,
        sandbox_dir: Path,
        session_store: SessionStore | None = None,
        agent_config: InProcessAgentConfig,
        telemetry: Telemetry | None = None,
    ) -> None:
        """Initialize the in-process service and its owned state."""
        self._settings = settings
        self._sandbox_dir = sandbox_dir
        self._telemetry = telemetry
        self._agent_config = agent_config
        self._model_registry, self._provider_registry = build_registries()
        self._session_manager = SessionManager(session_store or JsonSessionStore())
        self._agent: Agent | None = None

        if telemetry is not None:
            telemetry.initialize(settings)

    def _get_api_key(self, provider: str) -> tuple[str | None, ServiceStatus | None]:
        """Read the provider API key or return a status error."""
        try:
            return self._settings.get_api_key(provider), None
        except SecretsLoadError as error:
            return None, _api_key_error_status(error)

    def _connected_provider_ids(self) -> tuple[set[str], ServiceStatus | None]:
        """Return connected providers or a status error."""
        try:
            connected_provider_ids = {
                provider.id
                for provider in self.list_providers()
                if self._settings.get_api_key(provider.id)
            }
        except SecretsLoadError as error:
            return set(), _api_key_error_status(error)

        if not connected_provider_ids:
            return set(), _not_ready(
                summary="Provider setup required",
                detail="Connect a provider API key in settings to continue.",
            )

        return connected_provider_ids, None

    def _selection_status(self, connected_provider_ids: set[str]) -> ServiceStatus | None:
        """Validate the current provider and model selection."""
        provider = self._settings.provider
        model = self._settings.model
        if provider is None or model is None:
            return _not_ready(
                summary="Model selection required",
                detail="Select a model in settings to continue.",
            )

        if provider not in connected_provider_ids:
            return _not_ready(
                summary=f"Connect {provider} to continue",
                detail="The selected provider does not have an API key configured.",
            )

        try:
            self._provider_registry.get(provider)
            self._model_registry.get(provider, model)
        except Exception:
            return _not_ready(
                summary="Selected model unavailable",
                detail="Choose a different model in settings.",
            )

        return None

    def _credentials_status(self) -> ServiceStatus | None:
        """Validate credentials for the selected provider."""
        provider = self._settings.provider
        if provider is None:
            return _not_ready(
                summary="Model selection required",
                detail="Select a model in settings to continue.",
            )

        api_key, status = self._get_api_key(provider)
        if status is not None:
            return status
        if api_key is None:
            return _not_ready(summary=f"{provider} API key not configured")
        if not api_key.strip():
            return _not_ready(summary=f"{provider} API key cannot be empty")
        return None

    def _ensure_agent(self) -> ServiceStatus | None:
        """Build the cached agent if needed."""
        if self._agent is not None:
            return None

        try:
            self._agent = self._agent_config.build(
                self._settings,
                self._session_manager,
                sandbox_dir=self._sandbox_dir,
            )
        except StartupConfigurationError as error:
            return _startup_error_status(error)
        except SecretsLoadError as error:
            return _startup_error_status(startup_error_from_settings_error(error))
        except PermissionError as error:
            startup_error = StartupEnvironmentError.from_permission_error(error)
            return _startup_error_status(startup_error)

        return None

    def update_settings(self, settings: SettingsManager) -> None:
        """Replace settings and invalidate the cached agent."""
        self._settings = settings
        self._agent = None

    def ready(self) -> ServiceStatus:
        """Return whether the service is ready for chat."""
        connected_provider_ids, status = self._connected_provider_ids()
        if status is not None:
            return status

        status = self._selection_status(connected_provider_ids)
        if status is not None:
            return status

        status = self._credentials_status()
        if status is not None:
            return status

        status = self._ensure_agent()
        if status is not None:
            return status

        return ServiceStatus(is_ready=True, summary="Ready")

    def _require_ready(self) -> None:
        """Raise if the service is not ready for chat."""
        status = self.ready()
        if not status.is_ready:
            raise ServiceNotReadyError(summary=status.summary, detail=status.detail)

    def _require_agent(self) -> Agent:
        """Return the cached agent after readiness has been checked."""
        if self._agent is None:
            raise ServiceNotReadyError(summary="Service is not ready")
        return self._agent

    def _translate_chat_error(  # noqa: C901 - allow complex
        self,
        error: llm_exceptions.LLMError | tool_exceptions.ToolError,
    ) -> ServiceChatError:
        """Translate known runtime failures to service chat errors."""
        if isinstance(error, llm_exceptions.LLMAuthenticationError):
            return ServiceAuthenticationError(
                summary="Authentication failed.",
                detail=f"{error.message}\n\nPlease check your API key and try again.",
                message=error.message,
            )
        if isinstance(error, llm_exceptions.LLMRateLimitError):
            return ServiceRateLimitError(
                summary="Rate limit exceeded.",
                detail=f"{error.message}\n\nPlease check your plan and billing details.",
                message=error.message,
            )
        if isinstance(error, llm_exceptions.LLMConnectionError):
            return ServiceConnectionError(
                summary="Connection error.",
                detail=f"{error.message}\n\nPlease check your internet connection and try again.",
                message=error.message,
            )
        if isinstance(error, llm_exceptions.LLMAPIError):
            return ServiceProviderError(
                summary="Provider error.",
                detail=error.message,
                message=error.message,
            )
        if isinstance(error, (llm_exceptions.LLMError, tool_exceptions.ToolError)):
            message = str(error)
            return ServiceProviderError(
                summary="Request failed.",
                detail=message,
                message=message,
            )
        return ServiceProviderError(
            summary="Request failed.",
            detail=str(error),
            message=str(error),
        )

    async def chat(self, message: str) -> AsyncIterator[StreamEvent]:
        """Send a message and stream provider events."""
        self._require_ready()
        agent = self._require_agent()

        try:
            async for event in agent.run(message):
                yield map_llm_event_to_stream_event(event)
        except (llm_exceptions.LLMError, tool_exceptions.ToolError) as error:
            raise self._translate_chat_error(error) from error

    def list_providers(self) -> list[ProviderDefinition]:
        """List available providers."""
        providers = self._provider_registry.supported()
        return [
            map_provider_definition_to_contract_provider_definition(provider)
            for provider in providers
        ]

    def list_connected_providers(self) -> list[ProviderDefinition]:
        """List providers that currently have configured credentials."""
        try:
            connected_ids = {
                provider.id
                for provider in self._provider_registry.supported()
                if self._settings.get_api_key(provider.id)
            }
        except SecretsLoadError:
            return []

        providers = [
            provider
            for provider in self._provider_registry.supported()
            if provider.id in connected_ids
        ]
        return [
            map_provider_definition_to_contract_provider_definition(provider)
            for provider in providers
        ]

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        """List available models, optionally filtered by provider."""
        models = self._model_registry.supported(provider)
        return [map_model_definition_to_contract_model_definition(model) for model in models]

    def list_selectable_models(self) -> list[ModelDefinition]:
        """List models available for currently connected providers."""
        connected_providers = {provider.id for provider in self.list_connected_providers()}
        models = self._model_registry.supported()
        selectable_models = [model for model in models if model.provider in connected_providers]
        return [
            map_model_definition_to_contract_model_definition(model) for model in selectable_models
        ]

    def active_session(self) -> SessionInfo | None:
        """Get the currently active session, if any."""
        session = self._session_manager.active_session
        if session is None:
            return None
        return map_session_to_session_info(session)

    def list_sessions(self) -> list[SessionInfo]:
        """List available sessions."""
        sessions = self._session_manager.list_sessions()
        return [map_session_to_session_info(session) for session in sessions]

    def new_session(self) -> SessionInfo:
        """Create a new session."""
        session = self._session_manager.create_session()
        return map_session_to_session_info(session)

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, list[Message]]:
        """Switch to a session and return its mapped messages."""
        try:
            session = self._session_manager.switch_session(session_id)
        except SessionNotFoundError as error:
            raise ServiceSessionNotFoundError from error
        return (
            map_session_to_session_info(session),
            map_messages_to_contract_messages(session.messages),
        )

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session."""
        try:
            self._session_manager.delete_session(session_id)
        except SessionNotFoundError as error:
            raise ServiceSessionNotFoundError from error
