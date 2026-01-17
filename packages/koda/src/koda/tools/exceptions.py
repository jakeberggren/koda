"""Tool exceptions with agent-friendly error messages.

Design principles:
- Show the original path the agent passed, not resolved system paths
- Keep messages concise but actionable
- Provide hints for common fixes
- Avoid exposing unnecessary system details
"""


class ToolError(Exception):
    """Base exception for all tool-related errors."""


class FileNotFoundError(ToolError):
    """File or directory not found."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"File not found: '{path}' - verify the path exists")


class NotAFileError(ToolError):
    """Path exists but is not a file (e.g., it's a directory)."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Not a file: '{path}' is a directory")


class NotADirectoryError(ToolError):
    """Path exists but is not a directory."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Not a directory: '{path}' is a file")


class PermissionError(ToolError):
    """Permission denied by the operating system."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Permission denied: '{path}'")


class PathOutsideSandboxError(ToolError):
    """Path escapes the allowed directory."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Access denied: '{path}' is outside the allowed directory")


class PathDeniedError(ToolError):
    """Path is denied by policy (gitignore, denied components, etc.)."""

    def __init__(self, path: str, *, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Access denied: '{path}' - {reason}")


class MaxIterationsExceededError(ToolError):
    """Maximum tool call iterations exceeded."""

    def __init__(self, max_iterations: int) -> None:
        self.max_iterations = max_iterations
        super().__init__(f"Maximum tool iterations ({max_iterations}) exceeded")


class ToolAlreadyRegisteredError(ToolError):
    """Tool is already registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool '{name}' is already registered")
