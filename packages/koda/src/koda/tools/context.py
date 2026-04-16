from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from koda.tools.policy import ToolPolicy


@dataclass(slots=True)
class FileCoordinator:
    _locks: dict[Path, asyncio.Lock] = field(default_factory=dict)

    def lock_for(self, path: Path) -> asyncio.Lock:
        """Return the shared in-process lock for a resolved file path."""
        lock = self._locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[path] = lock
        return lock


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

    files: FileCoordinator
    """Coordinator for file locks to prevent race conditions."""

    @property
    def sandbox_dir(self) -> Path:
        """Root directory that tools are allowed to access."""
        return self.policy.sandbox_dir
