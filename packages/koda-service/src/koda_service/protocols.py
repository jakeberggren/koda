from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from koda.agents import Agent
from koda.sessions import SessionManager
from koda_common.settings import SettingsManager

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from uuid import UUID

    from koda_service.services.in_process.service import ServiceStatus
    from koda_service.types import SessionInfo

type AgentBuilder = Callable[[SettingsManager, SessionManager], Agent]


class KodaService[EventT, ProviderT, ModelT, MessageT](Protocol):
    """Composite service boundary used by Koda clients."""

    def ready(self) -> ServiceStatus:
        """Return the service status for the current configuration."""
        ...

    def update_settings(self, settings: SettingsManager) -> None:
        """Update the service settings."""
        ...

    def chat(self, message: str) -> AsyncIterator[EventT]:
        """Send a message and stream response events."""
        ...

    def list_providers(self) -> list[ProviderT]:
        """List available providers."""
        ...

    def list_connected_providers(self) -> list[ProviderT]:
        """List configured providers that currently have credentials."""
        ...

    def list_models(self, provider: str | None = None) -> list[ModelT]:
        """List available models, optionally filtered by provider."""
        ...

    def list_selectable_models(self) -> list[ModelT]:
        """List models for currently connected providers."""
        ...

    def active_session(self) -> SessionInfo:
        """Get the currently active session."""
        ...

    def list_sessions(self) -> list[SessionInfo]:
        """List available sessions."""
        ...

    def new_session(self) -> SessionInfo:
        """Create a new session."""
        ...

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, Sequence[MessageT]]:
        """Switch to a different session. Returns session info and messages."""
        ...

    def delete_session(self, session_id: UUID) -> SessionInfo | None:
        """Delete a session. Returns the new active session if the deleted one was active."""
        ...
