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
    StartupError,
)
from koda_service.models import (
    ChatRequest,
    ServiceDiagnostics,
    ServiceStatus,
    ServiceStatusCode,
)
from koda_service.protocols import KodaService
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

    def update_settings(self, settings: SettingsManager) -> None:
        """Replace settings and invalidate the cached agent."""
        self.settings = settings
        self.runtime.update_settings(settings)

    def status(self) -> ServiceStatus:
        """Return whether chat can run with the current settings, and if not, why."""
        try:
            return self._status()
        except SecretsLoadError as e:
            return ServiceStatus.from_startup_error(StartupError.from_secrets_load_error(e))

    def _status(self) -> ServiceStatus:
        if not any(model.is_connected(self.settings) for model in self.runtime.catalog.models()):
            return ServiceStatus(
                code=ServiceStatusCode.PROVIDER_SETUP_REQUIRED,
                summary="Provider setup required",
                detail="Connect provider credentials in settings to continue.",
            )
        provider, model_id = self.settings.provider, self.settings.model
        if provider is None or model_id is None:
            return ServiceStatus(
                code=ServiceStatusCode.MODEL_SELECTION_REQUIRED,
                summary="Model selection required",
                detail="Select a model in settings to continue.",
            )
        selected = self.get_model(provider, model_id)
        if selected is None or not selected.is_connected(self.settings):
            return ServiceStatus(
                code=ServiceStatusCode.MODEL_UNAVAILABLE,
                summary="Selected model unavailable",
                detail="Connect its provider or choose a different model in settings.",
            )
        return ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")

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
                if any(c.is_connected(self.settings) for c in provider.connections)
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

    def list_configured_models(self) -> list[Model]:
        """List models with a connected connection.

        A model's detail names its connection when its provider has more than one connected.
        """
        try:
            connected = [
                (model, model.connection(self.settings))
                for model in self.runtime.catalog.models()
                if model.is_connected(self.settings)
            ]
            several = {
                provider.id
                for provider in self.list_configured_providers()
                if sum(c.is_connected(self.settings) for c in provider.connections) > 1
            }
        except SecretsLoadError:
            return []
        return [
            replace(model, detail=connection.detail or model.detail)
            if model.provider in several
            else replace(model, detail=None)
            for model, connection in connected
        ]

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
