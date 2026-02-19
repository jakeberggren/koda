from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from koda_common.contracts import (
    BackendNoActiveSessionError,
    BackendSessionNotFoundError,
    KodaBackend,
)
from koda_tui.converters import convert_messages

if TYPE_CHECKING:
    from uuid import UUID

    from koda_common.contracts import ModelDefinition
    from koda_tui.state import AppState


class ModelSelectionSettings(Protocol):
    provider: str
    model: str


class AppearanceSettings(Protocol):
    theme: str
    show_scrollbar: bool
    queue_inputs: bool


class ProviderSettings(Protocol):
    def set_api_key(self, provider: str, key: str) -> None: ...


@dataclass(slots=True, frozen=True)
class ActionResult[T]:
    ok: bool
    payload: T | None = None
    error: str | None = None


# --- Session actions ---


def new_session(
    backend: KodaBackend,
    state: AppState,
) -> ActionResult[None]:
    """Create a new session and reset conversation state."""
    try:
        backend.new_session()
        state.reset_conversation()
        return ActionResult(ok=True)
    except BackendNoActiveSessionError:
        return ActionResult(ok=False, error="No active session available")


def switch_session(
    session_id: UUID,
    backend: KodaBackend,
    state: AppState,
) -> ActionResult[None]:
    """Switch to a session and sync conversation state."""
    try:
        _, messages = backend.switch_session(session_id)
        state.reset_conversation()
        state.messages = convert_messages(messages)
        return ActionResult(ok=True)
    except BackendSessionNotFoundError:
        return ActionResult(ok=False, error="Session not found")


@dataclass(slots=True, frozen=True)
class DeleteSessionPayload:
    removed_active_session: bool


def delete_session(
    session_id: UUID,
    backend: KodaBackend,
    state: AppState,
) -> ActionResult[DeleteSessionPayload]:
    """Delete a session and clear state if the active session was removed."""
    try:
        new_active = backend.delete_session(session_id)
        if new_active is None:
            return ActionResult(ok=True, payload=DeleteSessionPayload(removed_active_session=False))
        state.reset_conversation()
        return ActionResult(ok=True, payload=DeleteSessionPayload(removed_active_session=True))
    except BackendSessionNotFoundError:
        return ActionResult(ok=False, error="Session not found")


# --- Model actions ---


def select_model(
    model: ModelDefinition,
    settings: ModelSelectionSettings,
) -> ActionResult[None]:
    """Select an active model/provider pair in settings."""
    old_provider = settings.provider
    old_model = settings.model
    try:
        settings.provider = model.provider
        settings.model = model.id
        return ActionResult(ok=True)
    except ValueError:
        settings.provider = old_provider
        settings.model = old_model
        return ActionResult(ok=False, error="Invalid model selection")


# --- Provider actions ---


def set_provider_api_key(
    provider: str,
    key: str,
    settings: ProviderSettings,
) -> ActionResult[None]:
    """Set provider API key in settings."""
    settings.set_api_key(provider, key)
    return ActionResult(ok=True)


# --- Appearance/system settings actions ---


def toggle_theme(settings: AppearanceSettings) -> ActionResult[None]:
    """Toggle between dark and light theme."""
    settings.theme = "light" if settings.theme == "dark" else "dark"
    return ActionResult(ok=True)


def toggle_scrollbar(settings: AppearanceSettings) -> ActionResult[None]:
    """Toggle chat scrollbar visibility."""
    settings.show_scrollbar = not settings.show_scrollbar
    return ActionResult(ok=True)


def toggle_queue_inputs(settings: AppearanceSettings) -> ActionResult[None]:
    """Toggle queue-inputs behavior during streaming."""
    settings.queue_inputs = not settings.queue_inputs
    return ActionResult(ok=True)
