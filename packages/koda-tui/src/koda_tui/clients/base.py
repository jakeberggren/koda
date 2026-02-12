from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from koda.messages import Message
from koda.providers import ModelDefinition, ProviderEvent


class SessionInfo(BaseModel):
    session_id: UUID
    name: str
    message_count: int
    created_at: datetime


class Client(Protocol):
    """Protocol for TUI clients."""

    def reconfigure(self) -> None:
        """Rebuild internal state for the current settings, preserving sessions."""
        ...

    def chat(self, message: str) -> AsyncIterator[ProviderEvent]:
        """Send a message and stream response events."""
        ...

    def list_providers(self) -> list[str]:
        """List available providers."""
        ...

    def list_models(self, provider: str | None = None) -> list[ModelDefinition]:
        """List available models, optionally filtered by provider."""
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

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, Sequence[Message]]:
        """Switch to a different session. Returns session info and messages."""
        ...

    def delete_session(self, session_id: UUID) -> SessionInfo | None:
        """Delete a session. Returns the new active session if the deleted one was active."""
        ...
