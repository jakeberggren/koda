import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from koda.messages.messages import AssistantMessage, ToolMessage, UserMessage

SessionMessage = Annotated[
    AssistantMessage | ToolMessage | UserMessage,
    Field(discriminator="role"),
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Session(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=_utcnow)
    messages: list[SessionMessage] = Field(default_factory=list)
    name: str | None = None
