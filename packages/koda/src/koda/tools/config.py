from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.tools.context import ToolContext, ToolExecutionCoordinator
from koda.tools.policy import ToolPolicy
from koda.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from koda.execution import CommandExecutor


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Bundle of tool registry and execution context."""

    registry: ToolRegistry
    context: ToolContext

    @classmethod
    def builtins(
        cls,
        *,
        cwd: Path,
        sandbox_dir: Path,
        executor: CommandExecutor,
    ) -> ToolConfig:
        registry = ToolRegistry.builtins()
        context = ToolContext(
            cwd=cwd.resolve(),
            policy=ToolPolicy.create(sandbox_dir=sandbox_dir.resolve()),
            coordinator=ToolExecutionCoordinator(),
            executor=executor,
        )
        return cls(registry=registry, context=context)
