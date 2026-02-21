from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agents import Agent
from koda.providers import get_model_registry, get_provider_registry
from koda.providers.exceptions import ProviderAuthenticationError
from koda.sessions import JsonSessionStore, SessionManager
from koda.sessions.exceptions import NoActiveSessionError, SessionNotFoundError
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda_api.mappers import (
    map_messages_to_contract_messages,
    map_model_definition_to_contract_model_definition,
    map_provider_event_to_stream_event,
    map_session_to_session_info,
)
from koda_common.contracts import (
    BackendAuthenticationError,
    BackendNoActiveSessionError,
    BackendSessionNotFoundError,
    KodaBackend,
    Message,
    ModelDefinition,
    SessionInfo,
    StreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from pathlib import Path
    from uuid import UUID

    from koda.messages import Message as CoreMessage
    from koda.telemetry import Telemetry
    from koda_common.settings import SettingsManager


class InProcessBackend(KodaBackend[StreamEvent, ModelDefinition, Message]):
    """Backend that uses koda core directly."""

    def __init__(
        self,
        settings: SettingsManager,
        sandbox_dir: Path,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._settings = settings
        self._sandbox_dir = sandbox_dir
        self._telemetry = telemetry
        if self._telemetry:
            self._telemetry.initialize(self._settings)
        self._session_manager = SessionManager(JsonSessionStore())
        self._session_manager.create_session()
        self._agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Create and configure the agent with provider and tools."""
        provider = get_provider_registry().create(
            self._settings.provider, self._settings, model=self._settings.model
        )
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=self._sandbox_dir)
        tools = ToolConfig(registry=registry, context=context)
        return Agent(
            provider=provider,
            session_manager=self._session_manager,
            tools=tools,
        )

    def reconfigure(self) -> None:
        """Rebuild the agent for the current settings, preserving sessions."""
        self._agent = self._create_agent()

    async def chat(self, message: str) -> AsyncIterator[StreamEvent]:
        """Send a message and stream response events."""
        try:
            async for provider_event in self._agent.run(message):
                yield map_provider_event_to_stream_event(provider_event)
        except ProviderAuthenticationError as e:
            raise BackendAuthenticationError from e

    def list_providers(self) -> list[str]:
        """List available providers."""
        return get_provider_registry().supported()

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        """List available models, optionally filtered by provider."""
        core_models = get_model_registry().supported(provider)
        return [map_model_definition_to_contract_model_definition(model) for model in core_models]

    def active_session(self) -> SessionInfo:
        """Get the currently active session."""
        try:
            return map_session_to_session_info(self._agent.active_session)
        except NoActiveSessionError as e:
            raise BackendNoActiveSessionError from e

    def list_sessions(self) -> list[SessionInfo]:
        """List non-empty sessions."""
        return [map_session_to_session_info(s) for s in self._agent.list_sessions() if s.messages]

    def new_session(self) -> SessionInfo:
        """Create a new session."""
        session = self._agent.new_session()
        return map_session_to_session_info(session)

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, Sequence[Message]]:
        """Switch to a different session. Returns session info and messages."""
        try:
            session = self._agent.switch_session(session_id)
        except SessionNotFoundError as e:
            raise BackendSessionNotFoundError from e
        messages: list[CoreMessage] = list(session.messages)
        return map_session_to_session_info(session), map_messages_to_contract_messages(messages)

    def delete_session(self, session_id: UUID) -> SessionInfo | None:
        """Delete a session. Returns the new active session if the deleted one was active."""
        try:
            new_session = self._agent.delete_session(session_id)
        except SessionNotFoundError as e:
            raise BackendSessionNotFoundError from e
        if new_session is not None:
            return map_session_to_session_info(new_session)
        return None
