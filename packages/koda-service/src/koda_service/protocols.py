from collections.abc import AsyncIterator, Sequence
from typing import Protocol
from uuid import UUID

from koda_service.types import SessionInfo


class ChatService[EventT](Protocol):
    """Streaming chat behavior exposed by the service boundary."""

    def chat(self, message: str) -> AsyncIterator[EventT]:
        """Send a message and stream response events."""
        ...


class CatalogService[ModelT](Protocol):
    """Provider and model discovery exposed by the service boundary."""

    def list_providers(self) -> list[str]:
        """List available providers."""
        ...

    def list_models(self, provider: str | None = None) -> list[ModelT]:
        """List available models, optionally filtered by provider."""
        ...


class SessionService[MessageT](Protocol):
    """Session lifecycle behavior exposed by the service boundary."""

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


class KodaService[EventT, ModelT, MessageT](
    ChatService[EventT],
    CatalogService[ModelT],
    SessionService[MessageT],
    Protocol,
):
    """Composite service boundary used by Koda clients."""

    def reconfigure(self) -> None:
        """Rebuild internal state for the current settings, preserving sessions."""
        ...
