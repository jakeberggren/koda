from typing import Protocol

from koda.execution.models import ExecutionResult


class CommandExecutor(Protocol):
    """Protocol for executing shell commands."""

    async def run(
        self,
        *,
        command: str,
        cwd: str,
        sandbox_dir: str,
        timeout_seconds: float,
    ) -> ExecutionResult: ...
