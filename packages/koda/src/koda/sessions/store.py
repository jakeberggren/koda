from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Protocol

from pydantic import TypeAdapter

from koda.agent.hooks import Hook
from koda.paths import sessions_dir_path
from koda.sessions.exceptions import SessionNotFoundError
from koda.sessions.session import Session

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID


SESSION_ADAPTER = TypeAdapter(Session)


class SessionStore(Protocol):
    """Session persistence."""

    def save_session(self, session: Session) -> None:
        """Store ``session``, replacing any stored session with the same id."""
        ...

    def get_session(self, session_id: UUID) -> Session:
        """Get a session by id. Raises SessionNotFoundError if not found."""
        ...

    def list_sessions(self) -> list[Session]:
        """List all sessions, newest first."""
        ...

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session. Raises SessionNotFoundError if not found."""
        ...


class InMemorySessionStore(SessionStore):
    """In-memory implementation of the SessionStore protocol."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    def save_session(self, session: Session) -> None:
        """Store a copy of ``session``."""
        self._sessions[session.session_id] = copy.deepcopy(session)

    def get_session(self, session_id: UUID) -> Session:
        """Retrieve a copy of a session by its ID."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        return copy.deepcopy(self._sessions[session_id])

    def list_sessions(self) -> list[Session]:
        """List all sessions, newest first."""
        sessions = [copy.deepcopy(session) for session in self._sessions.values()]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session by id."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        del self._sessions[session_id]


class JsonSessionStore(SessionStore):
    """File-based session store using one JSON file per session."""

    def __init__(self, directory: Path | None = None) -> None:
        self._dir = directory or sessions_dir_path()
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_id: UUID) -> Path:
        return self._dir / f"{session_id}.json"

    def _read(self, path: Path) -> Session:
        return SESSION_ADAPTER.validate_json(path.read_bytes())

    def save_session(self, session: Session) -> None:
        self._path_for(session.session_id).write_bytes(SESSION_ADAPTER.dump_json(session, indent=2))

    def get_session(self, session_id: UUID) -> Session:
        path = self._path_for(session_id)
        if not path.exists():
            raise SessionNotFoundError(session_id)
        return self._read(path)

    def list_sessions(self) -> list[Session]:
        sessions = [self._read(p) for p in self._dir.glob("*.json")]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def delete_session(self, session_id: UUID) -> None:
        path = self._path_for(session_id)
        if not path.exists():
            raise SessionNotFoundError(session_id)
        path.unlink()


class SaveSessionHook(Hook):
    """Saves the session to ``store`` at each checkpoint."""

    def __init__(self, store: SessionStore) -> None:
        self.store = store

    async def on_checkpoint(self, session: Session) -> None:
        self.store.save_session(session)
