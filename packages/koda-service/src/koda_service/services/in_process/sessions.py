from __future__ import annotations

from typing import TYPE_CHECKING

from koda.sessions.exceptions import NoActiveSessionError, SessionNotFoundError
from koda_service.exceptions import (
    ServiceNoActiveSessionError,
    ServiceSessionNotFoundError,
)
from koda_service.mappers import map_messages_to_contract_messages, map_session_to_session_info

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from koda.messages import Message as CoreMessage
    from koda_service.types import Message, SessionInfo


class SessionService:
    """Session lifecycle adapter for the in-process service."""

    def __init__(self, agent) -> None:
        self._agent = agent

    def active_session(self) -> SessionInfo:
        try:
            return map_session_to_session_info(self._agent.active_session)
        except NoActiveSessionError as error:
            raise ServiceNoActiveSessionError from error

    def list_sessions(self) -> list[SessionInfo]:
        return [
            map_session_to_session_info(session)
            for session in self._agent.list_sessions()
            if session.messages
        ]

    def new_session(self) -> SessionInfo:
        session = self._agent.new_session()
        return map_session_to_session_info(session)

    def switch_session(self, session_id: UUID) -> tuple[SessionInfo, Sequence[Message]]:
        try:
            session = self._agent.switch_session(session_id)
        except SessionNotFoundError as error:
            raise ServiceSessionNotFoundError from error
        messages: list[CoreMessage] = list(session.messages)
        return map_session_to_session_info(session), map_messages_to_contract_messages(messages)

    def delete_session(self, session_id: UUID) -> SessionInfo | None:
        try:
            new_session = self._agent.delete_session(session_id)
        except SessionNotFoundError as error:
            raise ServiceSessionNotFoundError from error
        if new_session is None:
            return None
        return map_session_to_session_info(new_session)
