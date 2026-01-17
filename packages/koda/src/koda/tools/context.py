from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koda.tools.policy import ToolPolicy


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

    @property
    def sandbox_dir(self) -> Path:
        """Root directory that tools are allowed to access."""
        return self.policy.sandbox_dir

    @classmethod
    def default(cls, sandbox_dir: Path | None = None, cwd: Path | None = None) -> ToolContext:
        """Create a default tool context.

        Defaults:
        - sandbox_dir: Path.cwd()
        - cwd: Path.cwd()
        """
        resolved_cwd = (cwd or Path.cwd()).resolve()
        resolved_sandbox = (sandbox_dir or resolved_cwd).resolve()
        policy = ToolPolicy.create(sandbox_dir=resolved_sandbox)
        return cls(cwd=resolved_cwd, policy=policy)
