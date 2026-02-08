from uuid import UUID


class SessionError(Exception):
    """Base exception for all session-related errors."""


class SessionNotFoundError(SessionError):
    """Session not found."""

    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: '{session_id}'")


class NoActiveSessionError(SessionError):
    """No active session set."""
