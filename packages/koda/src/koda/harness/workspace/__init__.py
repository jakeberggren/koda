"""The workspace: the folder Koda works in, how paths in it resolve, what can be wrong with a
path, and the locks that let tools work in it in parallel."""

from koda.harness.workspace.exceptions import (
    AccessDeniedError,
    NotAFileError,
    NotAFolderError,
    PathNotFoundError,
)
from koda.harness.workspace.locks import Locks
from koda.harness.workspace.workspace import Workspace

__all__ = [
    "AccessDeniedError",
    "Locks",
    "NotAFileError",
    "NotAFolderError",
    "PathNotFoundError",
    "Workspace",
]
