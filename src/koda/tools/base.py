from typing import Any, Protocol

from pydantic import BaseModel


class Tool(Protocol):
    """Protocol for all tools that can be executed by the agent."""

    name: str
    """Unique identifier for the tool."""

    description: str
    """Human-readable description of what the tool does."""

    parameters_model: type[BaseModel]
    """Pydantic model for validating tool parameters."""

    async def execute(self, params: BaseModel) -> "ToolResult":
        """Execute the tool with validated parameters."""
        ...


class ToolDefinition(BaseModel):
    """Serializable definition of a tool for provider communication."""

    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    """Represents a request to execute a tool."""

    tool_name: str
    arguments: dict[str, Any]
    call_id: str | None = None


class ToolResult(BaseModel):
    """Represents the result of tool execution."""

    content: str | dict[str, Any] | list[Any] | None
    is_error: bool = False
    error_message: str | None = None
    call_id: str | None = None
