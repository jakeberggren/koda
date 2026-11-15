"""The workspace: the folder Koda works in, and how paths in it resolve."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from anyio import Path as AnyioPath

from koda.harness.workspace.exceptions import NotAFileError, NotAFolderError, PathNotFoundError
from koda.harness.workspace.locks import Locks


@dataclass(frozen=True, slots=True)
class Workspace:
    """The folder Koda works in. Tools resolve relative paths against ``root``; absolute
    paths work as they are. It doesn't restrict where tools go: bash can go anywhere."""

    root: Path
    locks: Locks = field(default_factory=Locks)

    def __post_init__(self) -> None:
        # Absolute and with symlinks resolved, like every path ``resolve`` returns, so they
        # compare: on macOS, /tmp is /private/tmp.
        object.__setattr__(self, "root", self.root.resolve())

    def resolve(self, path: str) -> Path:
        """``path`` as an absolute path: relative to ``root`` unless it is absolute."""
        given = Path(path)
        return (given if given.is_absolute() else self.root / given).resolve()

    async def existing(self, path: str) -> Path:
        """``path`` resolved, if something exists there."""
        resolved = self.resolve(path)
        if not await AnyioPath(resolved).exists():
            raise PathNotFoundError(path)
        return resolved

    async def file(self, path: str) -> Path:
        """``path`` resolved, if it is a file."""
        resolved = await self.existing(path)
        if not await AnyioPath(resolved).is_file():
            raise NotAFileError(path)
        return resolved

    async def folder(self, path: str) -> Path:
        """``path`` resolved, if it is a folder."""
        resolved = await self.existing(path)
        if not await AnyioPath(resolved).is_dir():
            raise NotAFolderError(path)
        return resolved
