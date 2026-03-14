from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from koda_common.contracts import (
    BackendNoActiveSessionError,
    BackendSessionNotFoundError,
    KodaBackend,
    ModelDefinition,
    ThinkingOptionId,
)
from koda_tui.converters import convert_messages
from koda_tui.utils.model_selection import normalize_thinking_option, supported_thinking_options

if TYPE_CHECKING:
    from uuid import UUID

    from koda_tui.state import AppState


class ModelSelectionSettings(Protocol):
    provider: str
    model: str
    thinking: ThinkingOptionId

    def update(self, **changes: object) -> None: ...


class ThinkingSettings(Protocol):
    thinking: ThinkingOptionId

    def set(self, name: str, value: object) -> None: ...


class AppearanceSettings(Protocol):
    theme: str
    show_scrollbar: bool
    queue_inputs: bool

    def set(self, name: str, value: object) -> None: ...


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


def select_model(
    current_model: ModelDefinition | None,
    model: ModelDefinition,
    settings: ModelSelectionSettings,
) -> ActionResult[None]:
    """Select an active model/provider pair in settings."""
    try:
        changes: dict[str, object] = {
            "provider": model.provider,
            "model": model.id,
        }
        normalized_thinking = normalize_thinking_option(
            settings.thinking,
            current_options=supported_thinking_options(current_model),
            new_options=supported_thinking_options(model),
        )
        if normalized_thinking != settings.thinking:
            changes["thinking"] = normalized_thinking
        settings.update(**changes)
        return ActionResult(ok=True)
    except ValueError:
        return ActionResult(ok=False, error="Invalid model selection")


def set_thinking(
    thinking: ThinkingOptionId,
    settings: ThinkingSettings,
) -> ActionResult[None]:
    """Set model thinking effort."""
    settings.set("thinking", thinking)
    return ActionResult(ok=True)


def cycle_thinking(
    options: list[ThinkingOptionId],
    settings: ThinkingSettings,
) -> ActionResult[ThinkingOptionId]:
    """Cycle to the next supported thinking level."""
    if not options:
        return ActionResult(ok=False, error="No supported thinking levels")

    try:
        current_index = options.index(settings.thinking)
    except ValueError:
        current_index = -1
    next_level = options[(current_index + 1) % len(options)]
    settings.set("thinking", next_level)
    return ActionResult(ok=True, payload=next_level)


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
    settings.set("theme", "light" if settings.theme == "dark" else "dark")
    return ActionResult(ok=True)


def toggle_scrollbar(settings: AppearanceSettings) -> ActionResult[None]:
    """Toggle chat scrollbar visibility."""
    settings.set("show_scrollbar", not settings.show_scrollbar)
    return ActionResult(ok=True)


def toggle_queue_inputs(settings: AppearanceSettings) -> ActionResult[None]:
    """Toggle queue-inputs behavior during streaming."""
    settings.set("queue_inputs", not settings.queue_inputs)
    return ActionResult(ok=True)
