"""The workspace: the folder Koda works in, how paths in it resolve, what can be wrong with a
path, and the locks that let tools work in it in parallel."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from koda.tools import ToolError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass(slots=True)
class ToolExecutionCoordinator:
    """Coordinate concurrent tool access.

    Lock ordering:
    1. Acquire `shared_access()` or `exclusive_access()` first.
    2. If path-level coordination is also needed, acquire `path_lock(path)` second.

    Keeping this order consistent avoids deadlocks between cross-tool gating and
    per-path serialization.
    """

    _condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    _path_locks: dict[Path, asyncio.Lock] = field(default_factory=dict)
    _shared_holders: int = 0
    _exclusive_active: bool = False
    _exclusive_waiters: int = 0

    def path_lock(self, path: Path) -> asyncio.Lock:
        """Return the shared in-process lock for a resolved file path."""
        lock = self._path_locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            self._path_locks[path] = lock
        return lock

    @asynccontextmanager
    async def shared_access(self) -> AsyncGenerator[None]:
        """Allow concurrent access unless an exclusive caller is queued or active."""
        async with self._condition:
            await self._condition.wait_for(
                lambda: not self._exclusive_active and self._exclusive_waiters == 0,
            )
            self._shared_holders += 1

        try:
            yield
        finally:
            async with self._condition:
                self._shared_holders -= 1
                if self._shared_holders == 0:
                    self._condition.notify_all()

    @asynccontextmanager
    async def exclusive_access(self) -> AsyncGenerator[None]:
        """Run with exclusive access when no shared participant is active."""
        async with self._condition:
            self._exclusive_waiters += 1
            try:
                await self._condition.wait_for(
                    lambda: not self._exclusive_active and self._shared_holders == 0,
                )
                self._exclusive_active = True
            finally:
                self._exclusive_waiters -= 1

        try:
            yield
        finally:
            async with self._condition:
                self._exclusive_active = False
                self._condition.notify_all()


@dataclass(frozen=True, slots=True)
class Workspace:
    """The folder Koda works in. Tools resolve relative paths against ``root``; absolute
    paths work as they are. It doesn't restrict where tools go: bash can go anywhere."""

    root: Path
    coordinator: ToolExecutionCoordinator = field(default_factory=ToolExecutionCoordinator)

    def resolve(self, path: str) -> Path:
        """``path`` as an absolute path: relative to ``root`` unless it is absolute."""
        given = Path(path)
        return (given if given.is_absolute() else self.root / given).resolve()


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
