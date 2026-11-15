"""What can be wrong with a path in the workspace."""

from koda.tools import ToolError


class PathNotFoundError(ToolError):
    """Nothing exists at the path."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"File not found: '{path}' - verify the path exists")


class NotAFileError(ToolError):
    """The path is a folder, not a file."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Not a file: '{path}' is a directory")


class NotAFolderError(ToolError):
    """The path is a file, not a folder."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Not a directory: '{path}' is a file")


class AccessDeniedError(ToolError):
    """The operating system refused access to the path."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Permission denied: '{path}'")
