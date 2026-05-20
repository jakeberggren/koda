from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from koda.messages import AssistantMessage
    from koda.tools import ToolCall, ToolResult


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
class AgentTextDelta:
    """Assistant text streamed from the current model iteration."""

    text: str


@dataclass(frozen=True, slots=True)
class AgentThinkingDelta:
    """Assistant thinking text streamed from the current model iteration."""

    text: str


@dataclass(frozen=True, slots=True)
class AgentToolCallRequested:
    """The model requested a tool call."""

    call: ToolCall


@dataclass(frozen=True, slots=True)
class AgentToolStarted:
    """Tool execution has started."""

    call: ToolCall


@dataclass(frozen=True, slots=True)
class AgentToolCompleted:
    """Tool execution has completed."""

    tool_name: str
    result: ToolResult


@dataclass(frozen=True, slots=True)
class AgentToolResultReady:
    """Tool execution result is available before ordered persistence."""

    tool_name: str
    result: ToolResult


@dataclass(frozen=True, slots=True)
class AgentResponseCompleted:
    """An assistant message was completed and persisted."""

    message: AssistantMessage


@dataclass(frozen=True, slots=True)
class AgentTurnCompleted:
    """A user turn completed without additional tool calls."""

    session_id: UUID
    iterations: int


AgentEvent = (
    AgentTurnStarted
    | AgentIterationStarted
    | AgentTextDelta
    | AgentThinkingDelta
    | AgentToolCallRequested
    | AgentToolStarted
    | AgentToolResultReady
    | AgentToolCompleted
    | AgentResponseCompleted
    | AgentTurnCompleted
)
