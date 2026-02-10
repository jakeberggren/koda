from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agents import Agent
from koda.providers import get_model_registry, get_provider_registry
from koda.sessions import InMemorySessionStore, SessionManager
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda_tui.clients import Client
from koda_tui.clients.base import SessionInfo

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path
    from uuid import UUID

    from koda.messages import Message
    from koda.providers.events import ProviderEvent
    from koda.sessions import Session
    from koda_common import SettingsManager
    from koda_tui.clients import ModelDefinition


class LocalClient(Client):
    """Client that uses koda core directly."""

    def __init__(self, settings: SettingsManager, sandbox_dir: Path) -> None:
        self._settings = settings
        self._sandbox_dir = sandbox_dir
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
            session_manager=SessionManager(InMemorySessionStore()),
            tools=tools,
        )

    def chat(self, message: str) -> AsyncIterator[ProviderEvent]:
        """Send a message and stream response events."""
        return self._agent.run(message)

    def list_providers(self) -> list[str]:
        """List available providers."""
        return get_provider_registry().supported()

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        """List available models, optionally filtered by provider."""
        return get_model_registry().supported(provider)

    def _to_session_info(self, session: Session) -> SessionInfo:
        if session.name:
            name = session.name
        elif session.messages:
            name = f"{session.messages[0].content[:30]}..."
        else:
            name = "New session"

        return SessionInfo(
            session_id=session.session_id,
            name=name,
            message_count=len(session.messages),
            created_at=session.created_at,
        )

    def active_session(self) -> SessionInfo:
        """Get the currently active session."""
        return self._to_session_info(self._agent.active_session)

    def list_sessions(self) -> list[SessionInfo]:
        """List non-empty sessions."""
        return [self._to_session_info(s) for s in self._agent.list_sessions() if s.messages]

    def new_session(self) -> SessionInfo:
        """Create a new session."""
        session = self._agent.new_session()
        return self._to_session_info(session)

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, list[Message]]:
        """Switch to a different session. Returns session info and messages."""
        session = self._agent.switch_session(session_id)
        return self._to_session_info(session), session.messages

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session."""
        self._agent.delete_session(session_id)
