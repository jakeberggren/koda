from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from koda.llm import ModelDefinition, ProviderDefinition, ThinkingOption
from koda.messages import TokenUsage
from koda.tools import ToolCall
from koda_service import ServiceStatus, ServiceStatusCode


class MessageRole(Enum):
    """Role of a message in the chat history."""

    USER = auto()
    ASSISTANT = auto()
    TOOL = auto()


class ResponsePhase(Enum):
    """Current phase of an in-flight response."""

    IDLE = auto()
    WORKING = auto()
    RESPONDING = auto()
    TOOLS = auto()


@dataclass
class Message:
    """A single message in the chat history."""

    role: MessageRole
    content: str
    thinking_content: str = ""
    tool_call: ToolCall | None = None
    tool_running: bool = False
    tool_error: bool = False
    tool_result_display: str | None = None
    tool_result_content: dict[str, Any] | None = None
    tool_error_message: str | None = None


@dataclass
class AppState:
    """Shared application state as single source of truth for the UI."""

    workspace_root: Path
    service_status: ServiceStatus = field(
        default_factory=lambda: ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")
    )
    warnings: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    current_streaming_content: str = ""
    current_thinking_content: str = ""
    is_streaming: bool = False
    is_thinking: bool = False
    response_phase: ResponsePhase = ResponsePhase.IDLE
    active_tools: dict[str, ToolCall] = field(default_factory=dict)
    pending_inputs: list[str] = field(default_factory=list)
    active_model: ModelDefinition | None = None
    configured_providers: list[ProviderDefinition] = field(default_factory=list)
    provider_id: str | None = None
    thinking: ThinkingOption = field(default_factory=ThinkingOption.none)
    context_window: int | None = None
    usage: TokenUsage | None = None
    total_usage: TokenUsage | None = None
    thinking_supported: bool = False
    show_scrollbar: bool = True
    queue_inputs: bool = True
    exit_requested: bool = False
    palette_open: bool = False

    def reset_conversation(self) -> None:
        """Clear all conversation and streaming state."""
        self.messages.clear()
        self.current_streaming_content = ""
        self.current_thinking_content = ""
        self.is_streaming = False
        self.is_thinking = False
        self.response_phase = ResponsePhase.IDLE
        self.active_tools.clear()
        self.usage = None
        self.total_usage = None
