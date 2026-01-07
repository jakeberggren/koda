from pathlib import Path


class ToolError(Exception):
    """Base exception for all tool-related errors."""


class ToolValidationError(ToolError):
    """Tool argument validation error."""


class ToolExecutionError(ToolError):
    """Tool execution error."""

    def __init__(self, message: str, path: str | Path | None = None) -> None:
        super().__init__(message)
        self.path = path


class ToolPermissionError(ToolExecutionError):
    """Permission denied during tool execution."""

    def __init__(self, path: str | Path) -> None:
        super().__init__(f"Permission denied: {path}", path)


class ToolReadError(ToolExecutionError):
    """Failed to read file."""

    def __init__(self, path: str | Path, error: Exception) -> None:
        super().__init__(f"Failed to read file: {error}", path)
        self.error = error


class ToolWriteError(ToolExecutionError):
    """Failed to write file."""

    def __init__(self, path: str | Path, error: Exception) -> None:
        super().__init__(f"Failed to write file: {error}", path)
        self.error = error


class ToolListDirectoryError(ToolExecutionError):
    """Failed to list directory."""

    def __init__(self, path: str | Path, error: Exception) -> None:
        super().__init__(f"Failed to list directory: {error}", path)
        self.error = error


class ToolFileSystemError(ToolError):
    """File system related errors."""


class ToolFileNotFoundError(ToolFileSystemError):
    """File or directory not found."""

    def __init__(self, path: Path, resource_type: str = "File") -> None:
        super().__init__(f"{resource_type} not found: {path}")
        self.path = path
        self.resource_type = resource_type


class ToolPathTypeError(ToolFileSystemError):
    """Path is not of expected type."""

    def __init__(self, path: Path, expected_type: str) -> None:
        super().__init__(f"Path is not a {expected_type}: {path}")
        self.path = path
        self.expected_type = expected_type


class PathOutsideSandboxError(ToolFileSystemError):
    """Path is outside the sandbox directory."""

    def __init__(self, path: Path, sandbox: Path) -> None:
        super().__init__(f"Path {path} is outside the sandbox directory {sandbox}")
        self.path = path
        self.sandbox = sandbox


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
