from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    role: MessageRole = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")

    def __str__(self) -> str:
        return f"{self.role.value}: {self.content}"


class UserMessage(Message):
    role: MessageRole = Field(default=MessageRole.USER, frozen=True)


class AssistantMessage(Message):
    role: MessageRole = Field(default=MessageRole.ASSISTANT, frozen=True)


class SystemMessage(Message):
    role: MessageRole = Field(default=MessageRole.SYSTEM, frozen=True)
