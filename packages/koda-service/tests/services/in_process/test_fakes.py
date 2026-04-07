from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from koda.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMRateLimitError,
)
from koda.messages import UserMessage as CoreUserMessage
from koda.sessions import Session


@dataclass(slots=True)
class FakeAgentBehavior:
    errors: dict[str, Exception] = field(default_factory=dict)
    delete_return: Session | None = None
    active_session: Session | None = None


class FakeAgent:
    def __init__(
        self,
        events: list[object] | None = None,
        session: Session | None = None,
        sessions: list[Session] | None = None,
        behavior: FakeAgentBehavior | None = None,
    ) -> None:
        behavior = behavior or FakeAgentBehavior()
        self._events = events or []
        self._session = session or Session()
        self._sessions = sessions or [self._session]
        self._delete_return = behavior.delete_return
        self._active_session = behavior.active_session or self._session
        self._errors = behavior.errors

    @property
    def active_session(self) -> Session:
        if active_session_error := self._errors.get("active_session"):
            raise active_session_error
        return self._active_session

    async def run(self, _message: str):
        for event in self._events:
            yield event

    def list_sessions(self) -> list[Session]:
        return self._sessions

    def new_session(self) -> Session:
        return self._session

    def switch_session(self, _session_id: UUID) -> Session:
        if switch_error := self._errors.get("switch_session"):
            raise switch_error
        return self._session

    def delete_session(self, _session_id: UUID) -> Session | None:
        if delete_error := self._errors.get("delete_session"):
            raise delete_error
        return self._delete_return


class RaisingAuthAgent:
    async def run(self, _message: str):
        raise LLMAuthenticationError("openai", Exception("bad key"))
        yield  # pragma: no cover


class RaisingRateLimitAgent:
    async def run(self, _message: str):
        raise LLMRateLimitError("openai", Exception("quota hit"))
        yield  # pragma: no cover


class RaisingConnectionAgent:
    async def run(self, _message: str):
        raise LLMConnectionError("openai", Exception("network down"))
        yield  # pragma: no cover


class RaisingApiAgent:
    async def run(self, _message: str):
        raise LLMAPIError("openai", Exception("server exploded"))
        yield  # pragma: no cover


def core_session(
    *,
    content: str = "hello",
    name: str | None = None,
    session_id: UUID | None = None,
) -> Session:
    return Session(
        session_id=session_id or uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        messages=[CoreUserMessage(content=content)],
        name=name,
    )
