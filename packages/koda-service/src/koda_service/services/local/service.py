from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agent import AgentEvent
from koda.context import ContextManager
from koda.llm import ModelDefinition, ProviderDefinition
from koda.llm import exceptions as llm_exceptions
from koda.messages import Message
from koda.sessions import JsonSessionStore, Session, SessionManager, SessionNotFoundError
from koda.tools import exceptions as tool_exceptions
from koda_common.settings import SecretsLoadError, SettingsManager
from koda_service.exceptions import (
    ServiceChatError,
    ServiceNotReadyError,
    ServiceSessionNotFoundError,
)
from koda_service.models import ChatRequest, ServiceDiagnostics, ServiceStatus
from koda_service.protocols import KodaService
from koda_service.services.local.availability import LocalAvailability
from koda_service.services.local.runtime import LocalRuntime

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from koda.sessions.store import SessionStore
    from koda.telemetry import Telemetry
    from koda_service.services.local.config import LocalRuntimeConfig


class LocalKodaService(KodaService[AgentEvent, ProviderDefinition, ModelDefinition, Message]):
    """Application service for running Koda inside the current process."""

    def __init__(
        self,
        *,
        settings: SettingsManager,
        runtime: LocalRuntimeConfig,
        session_store: SessionStore | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.settings = settings
        self.telemetry = telemetry
        self.session_manager = SessionManager(session_store or JsonSessionStore())
        self.runtime = LocalRuntime(
            settings=settings,
            config=runtime,
            session_manager=self.session_manager,
            context_manager=ContextManager.from_workspace(runtime.cwd),
        )
        self.availability = LocalAvailability(settings=settings, runtime=self.runtime)

        if telemetry is not None:
            telemetry.initialize(settings)

    def update_settings(self, settings: SettingsManager) -> None:
        """Replace settings and invalidate the cached agent."""
        self.settings = settings
        self.runtime.update_settings(settings)
        self.availability = LocalAvailability(settings=settings, runtime=self.runtime)

    def status(self) -> ServiceStatus:
        """Return the current service status."""
        return self.availability.status()

    async def chat(self, request: ChatRequest) -> AsyncIterator[AgentEvent]:  # noqa: C901 - allow complex
        """Send a message and stream agent events."""
        status = self.status()
        if not status.is_ready:  # require ready status for chat
            raise ServiceNotReadyError(summary=status.summary, detail=status.detail)

        if request.session_id is not None:
            self.switch_session(request.session_id)

        try:
            agent = await self.runtime.get_agent()
            async for event in agent.run(request.message):
                yield event
        except llm_exceptions.LLMError as error:
            raise ServiceChatError.from_llm_error(error) from error
        except tool_exceptions.ToolError as error:
            raise ServiceChatError.from_tool_error(error) from error

    def list_providers(self) -> list[ProviderDefinition]:
        """List available providers."""
        return self.runtime.llm_factory.list_providers()

    def list_configured_providers(self) -> list[ProviderDefinition]:
        """List providers that currently have configured credentials."""
        providers = self.list_providers()
        try:
            connected_ids = {
                provider.id
                for provider in providers
                if any(
                    self.settings.get_credential(f"{provider.id}:{connection.id}")
                    for connection in provider.connections
                )
            }
        except SecretsLoadError:
            return []

        return [provider for provider in providers if provider.id in connected_ids]

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        """List available models, optionally filtered by provider."""
        return self.runtime.llm_factory.list_models(provider)

    def get_model(self, provider: str | None, model_id: str | None) -> ModelDefinition | None:
        """Return a model by provider/model id, or None if unavailable."""
        if provider is None or model_id is None:
            return None
        return next(
            (
                model
                for model in self.runtime.llm_factory.list_models(provider)
                if model.id == model_id
            ),
            None,
        )

    def diagnostics(self) -> ServiceDiagnostics:
        """Return non-blocking service diagnostics."""
        warnings = [warning.summary for warning in self.runtime.warnings]
        return ServiceDiagnostics(startup_warnings=warnings)

    @staticmethod
    def _connection_credential_key(provider_id: str, connection_id: str) -> str:
        return f"{provider_id}:{connection_id}"

    def _configured_credential_ids(self) -> set[str]:
        return {
            self._connection_credential_key(provider.id, connection.id)
            for provider in self.list_providers()
            for connection in provider.connections
            if self.settings.get_credential(
                self._connection_credential_key(provider.id, connection.id)
            )
        }

    @staticmethod
    def _has_multiple_configured_connections(
        provider_id: str,
        credential_ids: set[str],
    ) -> bool:
        prefix = f"{provider_id}:"
        provider_credentials = [
            credential_id for credential_id in credential_ids if credential_id.startswith(prefix)
        ]
        return len(provider_credentials) > 1

    def _model_has_configured_connection(
        self,
        model: ModelDefinition,
        credential_ids: set[str],
    ) -> bool:
        return any(
            self._connection_credential_key(model.provider, connection_id) in credential_ids
            for connection_id in model.routes
        )

    def _configured_model_definition(
        self,
        model: ModelDefinition,
        credential_ids: set[str],
    ) -> ModelDefinition:
        route = self.runtime.llm_factory.resolve_route(
            model.provider,
            model.id,
            credential_ids=credential_ids,
        )
        detail = None
        if self._has_multiple_configured_connections(model.provider, credential_ids):
            detail = route.connection.detail or model.detail
        return model.model_copy(update={"detail": detail})

    def list_configured_models(self) -> list[ModelDefinition]:
        """List models with detail set to the effective configured connection."""
        models = self.runtime.llm_factory.list_models()
        try:
            credential_ids = self._configured_credential_ids()
            configured_models = [
                self._configured_model_definition(model, credential_ids)
                for model in models
                if self._model_has_configured_connection(model, credential_ids)
            ]
        except SecretsLoadError:
            return []
        else:
            return configured_models

    def active_session(self) -> Session | None:
        """Get the currently active session, if any."""
        return self.session_manager.active_session

    def list_sessions(self) -> list[Session]:
        """List available sessions."""
        return self.session_manager.list_sessions()

    def create_session(self) -> Session:
        """Create a new session."""
        session = self.session_manager.create_session()
        self.runtime.invalidate()
        return session

    def switch_session(self, session_id: UUID) -> Session:
        """Switch to a session."""
        active = self.session_manager.active_session
        active_session_id = active.session_id if active is not None else None
        try:
            session = self.session_manager.switch_session(session_id)
        except SessionNotFoundError as e:
            raise ServiceSessionNotFoundError from e
        else:
            if session.session_id != active_session_id:
                self.runtime.invalidate()
            return session

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session."""
        active = self.session_manager.active_session
        removing_active = active is not None and active.session_id == session_id
        try:
            self.session_manager.delete_session(session_id)
        except SessionNotFoundError as e:
            raise ServiceSessionNotFoundError from e
        else:
            if removing_active:
                self.runtime.invalidate()
