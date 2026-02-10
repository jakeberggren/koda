from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from koda.messages import Message
    from koda.sessions.session import Session
    from koda.sessions.store import SessionStore

from koda.sessions.exceptions import NoActiveSessionError


class SessionManager:
    """Manages session state on top of a SessionStore."""

    def __init__(self, store: SessionStore) -> None:
        self._store = store
        self._active_session_id: UUID | None = None

    @property
    def active_session(self) -> Session:
        """Get the currently active session."""
        if self._active_session_id is None:
            raise NoActiveSessionError
        return self._store.get_session(self._active_session_id)

    def _cleanup_empty_active(self) -> None:
        """Delete the active session if it has no messages."""
        if self._active_session_id is None:
            return
        session = self._store.get_session(self._active_session_id)
        if not session.messages:
            self._store.delete_session(self._active_session_id)

    def create_session(self) -> Session:
        """Create a new session and set it as active."""
        self._cleanup_empty_active()
        session = self._store.create_session()
        self._active_session_id = session.session_id
        return session

    def get_session(self, session_id: UUID) -> Session:
        """Get a session by id."""
        return self._store.get_session(session_id)

    def list_sessions(self) -> list[Session]:
        """List all sessions."""
        return self._store.list_sessions()

    def update_session(self, session: Session) -> Session:
        """Update a session."""
        return self._store.update_session(session)

    def switch_session(self, session_id: UUID) -> Session:
        """Switch the active session."""
        if session_id != self._active_session_id:
            self._cleanup_empty_active()
        session = self._store.get_session(session_id)
        self._active_session_id = session.session_id
        return session

    def append_message(self, session_id: UUID, message: Message) -> Session:
        """Append a message to a session."""
        return self._store.append_message(session_id, message)

    def delete_session(self, session_id: UUID) -> Session | None:
        """Delete a session. Returns the new active session if the deleted one was active."""
        is_active = session_id == self._active_session_id
        self._store.delete_session(session_id)
        if is_active:
            self._active_session_id = None
            return self.create_session()
        return None
