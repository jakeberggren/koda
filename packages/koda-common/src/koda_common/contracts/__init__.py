"""Shared client-boundary contracts for Koda.

This package exists to keep the boundary between clients (`koda-tui`, future apps)
and runtime implementations (`koda-api`, in-process adapters, HTTP adapters)
explicit and stable.

These schemas and protocols are intentionally transport-agnostic:
- Clients depend on `koda_common.contracts`, not on `koda` internals.
- `koda-api` implementations map core/runtime types to these contracts at the boundary.
"""

from koda_common.contracts.backend import KodaBackend, SessionInfo
from koda_common.contracts.events import (
    ProviderToolCompleted,
    ProviderToolStarted,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    ToolCallRequested,
    ToolCallResult,
)
from koda_common.contracts.exceptions import (
    BackendAuthenticationError,
    BackendNoActiveSessionError,
    BackendSessionNotFoundError,
)
from koda_common.contracts.messages import (
    AssistantMessage,
    Message,
    MessageRole,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from koda_common.contracts.models import (
    ModelCapability,
    ModelDefinition,
    ThinkingOption,
    ThinkingOptionDescription,
    ThinkingOptionId,
    ThinkingOptionLabel,
)
from koda_common.contracts.tools import ToolCall, ToolOutput, ToolResult

__all__ = [
    "AssistantMessage",
    "BackendAuthenticationError",
    "BackendNoActiveSessionError",
    "BackendSessionNotFoundError",
    "KodaBackend",
    "Message",
    "MessageRole",
    "ModelCapability",
    "ModelDefinition",
    "ProviderToolCompleted",
    "ProviderToolStarted",
    "SessionInfo",
    "StreamEvent",
    "SystemMessage",
    "TextDelta",
    "ThinkingDelta",
    "ThinkingOption",
    "ThinkingOptionDescription",
    "ThinkingOptionId",
    "ThinkingOptionLabel",
    "ToolCall",
    "ToolCallRequested",
    "ToolCallResult",
    "ToolMessage",
    "ToolOutput",
    "ToolResult",
    "UserMessage",
]
