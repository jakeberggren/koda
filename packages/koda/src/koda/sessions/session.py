import uuid

from pydantic import BaseModel, Field

from koda.messages.messages import Message


class Session(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    messages: list[Message] = Field(default_factory=list)
    name: str | None = None
