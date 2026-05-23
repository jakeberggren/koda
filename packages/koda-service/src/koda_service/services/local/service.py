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
        agent = self.runtime.get_agent()

        try:
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
                provider.id for provider in providers if self.settings.get_api_key(provider.id)
            }
        except SecretsLoadError:
            return []

        return [provider for provider in providers if provider.id in connected_ids]

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        """List available models, optionally filtered by provider."""
        return self.runtime.llm_factory.list_models(provider)

    def diagnostics(self) -> ServiceDiagnostics:
        """Return non-blocking service diagnostics."""
        warnings = [warning.summary for warning in self.runtime.warnings]
        return ServiceDiagnostics(startup_warnings=warnings)

    def list_configured_models(self) -> list[ModelDefinition]:
        """List models whose providers currently have configured credentials."""
        connected_providers = {provider.id for provider in self.list_configured_providers()}
        models = self.runtime.llm_factory.list_models()
        return [model for model in models if model.provider in connected_providers]

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
        try:
            session = self.session_manager.switch_session(session_id)
        except SessionNotFoundError as e:
            raise ServiceSessionNotFoundError from e
        else:
            self.runtime.invalidate()
            return session

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session."""
        try:
            self.session_manager.delete_session(session_id)
        except SessionNotFoundError as e:
            raise ServiceSessionNotFoundError from e
