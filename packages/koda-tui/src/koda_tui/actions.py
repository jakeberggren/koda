from dataclasses import dataclass
from uuid import UUID

from koda_common.contracts import (
    BackendNoActiveSessionError,
    BackendSessionNotFoundError,
    KodaBackend,
)
from koda_tui.converters import convert_messages
from koda_tui.state import AppState


@dataclass(slots=True, frozen=True)
class ActionResult[T]:
    ok: bool
    payload: T | None = None
    error: str | None = None


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
