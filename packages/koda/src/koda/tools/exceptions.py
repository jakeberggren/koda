from pathlib import Path


class ToolError(Exception):
    """Base exception for all tool-related errors."""


class FileNotFoundError(ToolError):
    """File or directory not found."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Not found: {path}")


class NotAFileError(ToolError):
    """Path is not a file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Not a file: {path}")


class NotADirectoryError(ToolError):
    """Path is not a directory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Not a directory: {path}")


class PermissionError(ToolError):
    """Permission denied during tool execution."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Permission denied: {path}")


class PathOutsideSandboxError(ToolError):
    """Path is outside the sandbox directory."""

    def __init__(self, path: Path, *, sandbox: Path) -> None:
        self.path = path
        self.sandbox = sandbox
        super().__init__(f"Path {path} is outside sandbox {sandbox}")


class PathDeniedError(ToolError):
    """Path is denied by policy."""

    def __init__(self, path: Path, *, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Access denied to {path}: {reason}")


class MaxIterationsExceededError(ToolError):
    """Maximum tool call iterations exceeded."""

    def __init__(self, max_iterations: int) -> None:
        self.max_iterations = max_iterations
        super().__init__(f"Maximum iterations ({max_iterations}) exceeded")


class ToolAlreadyRegisteredError(ToolError):
    """Tool is already registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool '{name}' already registered")
