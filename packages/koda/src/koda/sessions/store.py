from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import platformdirs

from koda.sessions.exceptions import SessionNotFoundError
from koda.sessions.session import Session

if TYPE_CHECKING:
    from uuid import UUID

    from koda.sessions.session import SessionMessage


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

    def append_message(self, session_id: UUID, message: SessionMessage) -> Session:
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
        return sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)

    def update_session(self, session: Session) -> Session:
        """Update an existing session."""
        if session.session_id not in self._sessions:
            raise SessionNotFoundError(session.session_id)
        self._sessions[session.session_id] = session
        return session

    def append_message(self, session_id: UUID, message: SessionMessage) -> Session:
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


_DEFAULT_DIR = Path(platformdirs.user_data_dir("koda", appauthor=False)) / "sessions"


class JsonSessionStore:
    """File-based session store using one JSON file per session."""

    def __init__(self, directory: Path = _DEFAULT_DIR) -> None:
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_id: UUID) -> Path:
        return self._dir / f"{session_id}.json"

    def _write(self, session: Session) -> None:
        data = session.model_dump(mode="json")
        self._path_for(session.session_id).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read(self, path: Path) -> Session:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session.model_validate(data)

    def create_session(self) -> Session:
        session = Session()
        self._write(session)
        return session

    def get_session(self, session_id: UUID) -> Session:
        path = self._path_for(session_id)
        if not path.exists():
            raise SessionNotFoundError(session_id)
        return self._read(path)

    def list_sessions(self) -> list[Session]:
        sessions = [self._read(p) for p in self._dir.glob("*.json")]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def update_session(self, session: Session) -> Session:
        path = self._path_for(session.session_id)
        if not path.exists():
            raise SessionNotFoundError(session.session_id)
        self._write(session)
        return session

    def append_message(self, session_id: UUID, message: SessionMessage) -> Session:
        session = self.get_session(session_id)
        session.messages.append(message)
        self._write(session)
        return session

    def delete_session(self, session_id: UUID) -> None:
        path = self._path_for(session_id)
        if not path.exists():
            raise SessionNotFoundError(session_id)
        path.unlink()
