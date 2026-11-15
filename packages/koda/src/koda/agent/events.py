"""What the agent streams: the model's events as they come, and the agent's own."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.llm.types import (
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
    LLMToolCompleted,
    LLMToolStarted,
)

if TYPE_CHECKING:
    from uuid import UUID

    from koda.messages import AssistantMessage, ToolCall, ToolMessage


@dataclass(frozen=True, slots=True)
class AgentTurnStarted:
    """A user turn has started in a session."""

    session_id: UUID


@dataclass(frozen=True, slots=True)
class AgentIterationStarted:
    """A model iteration has started within the current user turn."""

    session_id: UUID
    iteration: int


@dataclass(frozen=True, slots=True)
class AgentToolStarted:
    """Tool execution has started."""

    call: ToolCall


@dataclass(frozen=True, slots=True)
class AgentToolCompleted:
    """A tool's answer was added to the session."""

    message: ToolMessage


@dataclass(frozen=True, slots=True)
class AgentToolResultReady:
    """A tool's answer is ready; it is added to the session in call order."""

    message: ToolMessage


@dataclass(frozen=True, slots=True)
class AgentResponseCompleted:
    """An assistant message was completed."""

    message: AssistantMessage


@dataclass(frozen=True, slots=True)
class AgentTurnCompleted:
    """A user turn completed without additional tool calls."""

    session_id: UUID
    iterations: int


AgentEvent = (
    LLMTextDelta
    | LLMThinkingDelta
    | LLMToolCallRequested
    | LLMToolStarted  # A tool the provider runs, such as web search.
    | LLMToolCompleted
    | AgentTurnStarted
    | AgentIterationStarted
    | AgentToolStarted  # A tool Koda runs.
    | AgentToolResultReady
    | AgentToolCompleted
    | AgentResponseCompleted
    | AgentTurnCompleted
)
