"""File tool exceptions with agent-friendly error messages.

Design principles:
- Show the original path the agent passed, not resolved system paths
- Keep messages concise but actionable
- Provide hints for common fixes
- Avoid exposing unnecessary system details
"""

from koda.tools import ToolError


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
