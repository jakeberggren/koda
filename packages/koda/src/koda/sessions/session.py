import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from koda.messages.messages import AssistantMessage, TokenUsage, ToolMessage, UserMessage

SessionMessage = Annotated[
    AssistantMessage | ToolMessage | UserMessage,
    Field(discriminator="role"),
]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sum_usage_value(current: int | None, delta: int | None) -> int | None:
    if current is None:
        return delta
    if delta is None:
        return current
    return current + delta


def sum_usage(current: TokenUsage | None, delta: TokenUsage | None) -> TokenUsage | None:
    """Add token usage values while preserving unknown values as None."""
    if current is None:
        return delta
    if delta is None:
        return current
    return TokenUsage(
        input_tokens=_sum_usage_value(current.input_tokens, delta.input_tokens),
        output_tokens=_sum_usage_value(current.output_tokens, delta.output_tokens),
        cached_tokens=_sum_usage_value(current.cached_tokens, delta.cached_tokens),
        total_tokens=_sum_usage_value(current.total_tokens, delta.total_tokens),
    )


class Session(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=_utcnow)
    messages: list[SessionMessage] = Field(default_factory=list)
    name: str | None = None

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.messages:
            return f"{self.messages[0].content[:30]}..."
        return "New session"

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def usage(self) -> TokenUsage | None:
        """Return usage from the latest assistant message that has usage."""
        for message in reversed(self.messages):
            if isinstance(message, AssistantMessage) and message.usage is not None:
                return message.usage
        return None

    @property
    def total_usage(self) -> TokenUsage | None:
        """Return accumulated usage across assistant messages in this session."""
        total_usage: TokenUsage | None = None
        for message in self.messages:
            if isinstance(message, AssistantMessage):
                total_usage = sum_usage(total_usage, message.usage)
        return total_usage
