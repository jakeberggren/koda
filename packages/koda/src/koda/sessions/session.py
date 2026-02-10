import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from koda.messages.messages import Message


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Session(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=_utcnow)
    messages: list[Message] = Field(default_factory=list)
    name: str | None = None
