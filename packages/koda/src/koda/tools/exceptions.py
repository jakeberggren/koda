from pathlib import Path


class ToolError(Exception):
    """Base exception for all tool-related errors."""


class ToolValidationError(ToolError):
    """Tool argument validation error."""


class ToolExecutionError(ToolError):
    """Tool execution error."""


class MaxIterationsExceededError(ToolError):
    """Maximum tool call iterations exceeded."""

    def __init__(self, max_iterations: int) -> None:
        super().__init__(f"Maximum tool call iterations ({max_iterations}) exceeded")
        self.max_iterations = max_iterations


class ToolAlreadyRegisteredError(ToolError):
    """Tool is already registered."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(f"Tool '{tool_name}' is already registered")
        self.tool_name = tool_name


class ToolFileNotFoundError(ToolError):
    """File or directory not found."""

    def __init__(self, path: str, resource_type: str = "File") -> None:
        super().__init__(f"{resource_type} not found: {path}")
        self.path = path
        self.resource_type = resource_type


class ToolPathTypeError(ToolError):
    """Path is not of expected type."""

    def __init__(self, path: str, expected_type: str) -> None:
        super().__init__(f"Path is not a {expected_type}: {path}")
        self.path = path
        self.expected_type = expected_type


class PathOutsideSandboxError(ToolValidationError):
    """Path is outside the sandbox directory."""

    def __init__(self, path: Path, sandbox: Path) -> None:
        super().__init__(f"Path {path} is outside the sandbox directory {sandbox}")
        self.path = path
        self.sandbox = sandbox
