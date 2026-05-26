from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from koda.sessions import Session
    from koda_common.settings import SettingsManager
    from koda_service.models import ChatRequest, ServiceDiagnostics, ServiceStatus


class KodaService[EventT, ProviderT, ModelT, MessageT](Protocol):
    """Composite service boundary used by Koda clients."""

    def status(self) -> ServiceStatus:
        """Return the service status for the current configuration."""
        ...

    def update_settings(self, settings: SettingsManager) -> None:
        """Update the service settings."""
        ...

    def chat(self, request: ChatRequest) -> AsyncIterator[EventT]:
        """Send a message and stream response events."""
        ...

    def list_providers(self) -> list[ProviderT]:
        """List available providers."""
        ...

    def list_configured_providers(self) -> list[ProviderT]:
        """List configured providers that currently have credentials."""
        ...

    def list_models(self, provider: str | None = None) -> list[ModelT]:
        """List available models, optionally filtered by provider."""
        ...

    def get_model(self, provider: str | None, model_id: str | None) -> ModelT | None:
        """Return a model by provider/model id, or None if unavailable."""
        ...

    def diagnostics(self) -> ServiceDiagnostics:
        """Return non-blocking service diagnostics."""
        ...

    def list_configured_models(self) -> list[ModelT]:
        """List models whose providers currently have configured credentials."""
        ...

    def active_session(self) -> Session | None:
        """Get the currently active session, if any."""
        ...

    def list_sessions(self) -> list[Session]:
        """List available sessions."""
        ...

    def create_session(self) -> Session:
        """Create a new session."""
        ...

    def switch_session(self, session_id: UUID) -> Session:
        """Switch to a different session."""
        ...

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session."""
        ...
