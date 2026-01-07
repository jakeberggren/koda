class ToolError(Exception):
    """Base exception for all tool-related errors."""


class ToolValidationError(ToolError):
    """Tool argument validation error."""


class ToolExecutionError(ToolError):
    """Tool execution error."""


class MaxIterationsExceededError(ToolError):
    """Maximum tool call iterations exceeded."""
