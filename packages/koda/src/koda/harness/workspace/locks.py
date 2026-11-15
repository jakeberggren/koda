"""The locks tools take to work in the workspace in parallel."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@dataclass(slots=True)
class Locks:
    """The locks tools take to work in the workspace in parallel: ``shared`` for tools that
    run alongside each other (the file tools), ``exclusive`` for one that runs alone (bash,
    which can touch any file), and one per path, so writes to a file take turns.

    Take ``shared`` or ``exclusive`` first, then a path's lock, to avoid deadlocks.
    """

    _condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    _path_locks: dict[Path, asyncio.Lock] = field(default_factory=dict)
    _shared_holders: int = 0
    _exclusive_active: bool = False
    _exclusive_waiters: int = 0

    def path(self, path: Path) -> asyncio.Lock:
        """The lock for the resolved ``path``."""
        lock = self._path_locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            self._path_locks[path] = lock
        return lock

    @asynccontextmanager
    async def shared(self) -> AsyncGenerator[None]:
        """Run alongside other shared holders, once no exclusive one is running or waiting."""
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
    async def exclusive(self) -> AsyncGenerator[None]:
        """Run alone, once no shared holder is running."""
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
