from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from koda.agent import AgentEvent
from koda.context import ContextManager
from koda.llm import Model, Provider
from koda.llm import exceptions as llm_exceptions
from koda.messages import Message
from koda.sessions import JsonSessionStore, Session, SessionNotFoundError
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
    from koda_service.services.local.config import LocalRuntimeConfig


class LocalKodaService(KodaService[AgentEvent, Provider, Model, Message]):
    """Application service for running Koda inside the current process."""

    def __init__(
        self,
        *,
        settings: SettingsManager,
        runtime: LocalRuntimeConfig,
        session_store: SessionStore | None = None,
    ) -> None:
        self.settings = settings
        self.session_store = session_store or JsonSessionStore()
        self.session: Session | None = None
        self.runtime = LocalRuntime(
            settings=settings,
            config=runtime,
            session_store=self.session_store,
            context_manager=ContextManager.from_workspace(runtime.cwd),
        )
        self.availability = LocalAvailability(settings=settings, runtime=self.runtime)

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
        if self.session is None:
            self.session = Session()

        try:
            agent = await self.runtime.get_agent(self.session)
            async for event in agent.run(request.message):
                yield event
        except llm_exceptions.LLMError as error:
            raise ServiceChatError.from_llm_error(error) from error
        except tool_exceptions.ToolError as error:
            raise ServiceChatError.from_tool_error(error) from error

    def list_providers(self) -> list[Provider]:
        """List available providers."""
        return self.runtime.catalog.providers()

    def list_configured_providers(self) -> list[Provider]:
        """List providers that currently have configured credentials."""
        try:
            return [
                provider
                for provider in self.list_providers()
                if any(
                    self.settings.get_credential(connection.credential_key)
                    for connection in provider.connections
                )
            ]
        except SecretsLoadError:
            return []

    def list_models(self, provider: str | None = None) -> list[Model]:
        """List available models, optionally filtered by provider."""
        return self.runtime.catalog.models(provider)

    def get_model(self, provider: str | None, model_id: str | None) -> Model | None:
        """Return a model by provider/model id, or None if unavailable."""
        if provider is None or model_id is None:
            return None
        try:
            return self.runtime.catalog.model(provider, model_id)
        except llm_exceptions.LLMConfigurationError:
            return None

    def diagnostics(self) -> ServiceDiagnostics:
        """Return non-blocking service diagnostics."""
        warnings = [warning.summary for warning in self.runtime.warnings]
        return ServiceDiagnostics(startup_warnings=warnings)

    def _connected_keys(self) -> set[str]:
        return {
            connection.credential_key
            for provider in self.list_providers()
            for connection in provider.connections
            if self.settings.get_credential(connection.credential_key)
        }

    def _configured_model(self, model: Model, connected: set[str]) -> Model:
        """``model``, its detail naming its connection if its provider has several connected."""
        if sum(key.startswith(f"{model.provider}:") for key in connected) <= 1:
            return replace(model, detail=None)
        return replace(model, detail=model.connection(self.settings).detail or model.detail)

    def list_configured_models(self) -> list[Model]:
        """List models with a connected connection."""
        try:
            connected = self._connected_keys()
            return [
                self._configured_model(model, connected)
                for model in self.runtime.catalog.models()
                if any(connection.credential_key in connected for connection in model.connections)
            ]
        except SecretsLoadError:
            return []

    def active_session(self) -> Session | None:
        """Get the current session, if any."""
        return self.session

    def list_sessions(self) -> list[Session]:
        """List saved sessions."""
        return self.session_store.list_sessions()

    def create_session(self) -> Session:
        """Start a new session. It is saved once it has a message."""
        self.session = Session()
        self.runtime.invalidate()
        return self.session

    def switch_session(self, session_id: UUID) -> Session:
        """Switch to a saved session."""
        if self.session is not None and self.session.session_id == session_id:
            return self.session
        try:
            self.session = self.session_store.get_session(session_id)
        except SessionNotFoundError as e:
            raise ServiceSessionNotFoundError from e
        self.runtime.invalidate()
        return self.session

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session. Deleting the current one leaves no current session."""
        removing_current = self.session is not None and self.session.session_id == session_id
        try:
            self.session_store.delete_session(session_id)
        except SessionNotFoundError as e:
            if not removing_current:  # The current session may not be saved yet.
                raise ServiceSessionNotFoundError from e
        if removing_current:
            self.session = None
            self.runtime.invalidate()
