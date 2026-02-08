from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from koda.sessions.exceptions import SessionNotFoundError
from koda.sessions.session import Session

if TYPE_CHECKING:
    from uuid import UUID

    from koda.messages import Message


class SessionStore(Protocol):
    """Protocol for session persistence with CRUD operations."""

    def create_session(self) -> Session:
        """Create and store a new session."""
        ...

    def get_session(self, session_id: UUID) -> Session:
        """Get a session by id. Raises SessionNotFoundError if not found."""
        ...

    def list_sessions(self) -> list[Session]:
        """List all sessions, newest first."""
        ...

    def update_session(self, session: Session) -> Session:
        """Update a session. Raises SessionNotFoundError if not found."""
        ...

    def append_message(self, session_id: UUID, message: Message) -> Session:
        """Append a message to a session. Raises SessionNotFoundError if not found."""
        ...

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session. Raises SessionNotFoundError if not found."""
        ...


class InMemorySessionStore(SessionStore):
    """In-memory implementation of the SessionStore protocol."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    def create_session(self) -> Session:
        """Create and store a new session."""
        session = Session()
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: UUID) -> Session:
        """Retrieve a session by its ID."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        return self._sessions[session_id]

    def list_sessions(self) -> list[Session]:
        """List all sessions, newest first."""
        return list(reversed(self._sessions.values()))

    def update_session(self, session: Session) -> Session:
        """Update an existing session."""
        if session.session_id not in self._sessions:
            raise SessionNotFoundError(session.session_id)
        self._sessions[session.session_id] = session
        return session

    def append_message(self, session_id: UUID, message: Message) -> Session:
        """Append message to a session."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        self._sessions[session_id].messages.append(message)
        return self._sessions[session_id]

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session by id."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        del self._sessions[session_id]
