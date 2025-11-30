"""Core abstractions for the agents framework."""

from agents.core.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    UserMessage,
)

__all__ = [
    "AssistantMessage",
    "Message",
    "SystemMessage",
    "UserMessage",
]
