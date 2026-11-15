"""The workspace: the folder Koda works in, its files, how paths in it resolve, what can be
wrong with a path, and the locks that let tools work in it in parallel."""

from koda.harness.workspace.exceptions import (
    AccessDeniedError,
    NotAFileError,
    NotAFolderError,
    PathNotFoundError,
)
from koda.harness.workspace.ignore import SKIPPED
from koda.harness.workspace.locks import Locks
from koda.harness.workspace.workspace import Workspace

__all__ = [
    "SKIPPED",
    "AccessDeniedError",
    "Locks",
    "NotAFileError",
    "NotAFolderError",
    "PathNotFoundError",
    "Workspace",
]
