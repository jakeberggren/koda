from collections.abc import AsyncIterator, Sequence
from typing import Protocol
from uuid import UUID

from koda_service.types import SessionInfo


class KodaRuntime[EventT, MessageT](Protocol):
    """Agent runtime behavior exposed by the service boundary."""

    def chat(self, message: str) -> AsyncIterator[EventT]:
        """Run the agent on an event and return a message."""
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


class CatalogService[ProviderT, ModelT](Protocol):
    """Provider and model discovery exposed by the service boundary."""

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
