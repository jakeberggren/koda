"""The workspace: the folder Koda works in, its files, and how paths in it resolve."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from anyio import Path as AnyioPath

from koda.harness.workspace.exceptions import NotAFileError, NotAFolderError, PathNotFoundError
from koda.harness.workspace.ignore import SKIPPED, ignored, read_rules
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

    def files(self, folder: Path | None = None) -> list[str]:
        """The files in ``folder`` (the root by default), relative to it and sorted, as they
        are on disk now. Left out: what a .gitignore or .ignore on the way excludes, the
        deepest one with a say deciding, as in Git; and ``SKIPPED``."""
        folder = folder or self.root
        # The ignore files above ``folder``, from the root down, apply to it too.
        above = [path for path in reversed(folder.parents) if path.is_relative_to(self.root)]
        stacks = {folder.parent: tuple(rules for path in above if (rules := read_rules(path)))}
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(folder):
            current = Path(dirpath)
            stack = stacks[current.parent]
            if rules := read_rules(current):
                stack = (*stack, rules)
            stacks[current] = stack
            dirnames[:] = [
                name
                for name in dirnames
                if name not in SKIPPED and not ignored(stack, current / name, folder=True)
            ]
            files.extend(
                (current / name).relative_to(folder).as_posix()
                for name in filenames
                if name not in SKIPPED and not ignored(stack, current / name)
            )
        return sorted(files)

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
