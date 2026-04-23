from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from koda.execution import CommandExecutor
    from koda.tools.policy import ToolPolicy


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
    async def shared_access(self) -> AsyncIterator[None]:
        """Allow concurrent access unless an exclusive caller is queued or active."""
        async with self._condition:
            await self._condition.wait_for(
                lambda: not self._exclusive_active and self._exclusive_waiters == 0
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
    async def exclusive_access(self) -> AsyncIterator[None]:
        """Run with exclusive access when no shared participant is active."""
        async with self._condition:
            self._exclusive_waiters += 1
            try:
                await self._condition.wait_for(
                    lambda: not self._exclusive_active and self._shared_holders == 0
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
class ToolContext:
    """Execution context available to all tools.

    This is intentionally small and focused. Add fields here when multiple tools
    need the same shared dependency/configuration.
    """

    cwd: Path
    """Current working directory used for resolving relative paths."""

    policy: ToolPolicy
    """Policy object that enforces sandboxing and other safety limits."""

    coordinator: ToolExecutionCoordinator
    """Coordinator for shared/exclusive access and path-level serialization."""

    executor: CommandExecutor
    """Shared command executor used by tools that run shell commands."""

    @property
    def sandbox_dir(self) -> Path:
        """Root directory that tools are allowed to access."""
        return self.policy.sandbox_dir
