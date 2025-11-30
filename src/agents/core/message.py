"""Message models for agent communication."""

from enum import Enum

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Base message model for agent communication.

    This is a provider-agnostic message format that can be converted
    to provider-specific formats as needed.
    """

    role: MessageRole = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The message content")

    def __str__(self) -> str:
        """Return string representation of the message."""
        return f"{self.role.value}: {self.content}"


class UserMessage(Message):
    """User message."""

    role: MessageRole = Field(default=MessageRole.USER, frozen=True)


class AssistantMessage(Message):
    """Assistant message."""

    role: MessageRole = Field(default=MessageRole.ASSISTANT, frozen=True)


class SystemMessage(Message):
    """System message."""

    role: MessageRole = Field(default=MessageRole.SYSTEM, frozen=True)
