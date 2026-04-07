from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMRateLimitError,
)
from koda.sessions.exceptions import NoActiveSessionError, SessionNotFoundError
from koda_service.exceptions import (
    ServiceAuthenticationError,
    ServiceChatError,
    ServiceConnectionError,
    ServiceNoActiveSessionError,
    ServiceProviderError,
    ServiceRateLimitError,
    ServiceSessionNotFoundError,
)
from koda_service.mappers import (
    map_llm_event_to_stream_event,
    map_messages_to_contract_messages,
    map_session_to_session_info,
)
from koda_service.protocols import KodaRuntime
from koda_service.types import Message, StreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from uuid import UUID

    from koda.messages import Message as CoreMessage
    from koda_service.types import SessionInfo


def _translate_llm_error(error: LLMAPIError) -> ServiceChatError:
    match error:
        case LLMAuthenticationError():
            return ServiceAuthenticationError(
                summary="Authentication failed.",
                detail=(
                    "Please check your API key. Press `Ctrl+P` → `Connect Provider` to update it."
                ),
                message=str(error),
            )
        case LLMRateLimitError():
            return ServiceRateLimitError(
                summary="Rate limit exceeded.",
                detail=f"{error}\n\nPlease check your plan and billing details.",
                message=str(error),
            )
        case LLMConnectionError():
            return ServiceConnectionError(
                summary="Connection error.",
                detail=f"{error}\n\nPlease check your internet connection and try again.",
                message=str(error),
            )
        case _:
            return ServiceProviderError(
                summary="Provider error.",
                detail=str(error),
            )


class InProcessKodaRuntime(KodaRuntime[StreamEvent, Message]):
    """Stateful in-process runtime adapter around a single agent instance."""

    def __init__(self, agent) -> None:
        self._agent = agent

    async def chat(self, message: str) -> AsyncIterator[StreamEvent]:
        try:
            async for llm_event in self._agent.run(message):
                yield map_llm_event_to_stream_event(llm_event)
        except LLMAPIError as error:
            raise _translate_llm_error(error) from error

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
