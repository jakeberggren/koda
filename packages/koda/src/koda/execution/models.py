from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Structured result from command execution."""

    stdout: str
    stderr: str
    exit_code: int
    cwd: str
