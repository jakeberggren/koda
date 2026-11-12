from dataclasses import dataclass
from typing import Literal

type Sandbox = Literal["host", "seatbelt"]
"""Where commands run: directly on the host, or in a macOS seatbelt sandbox."""


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Structured result from command execution."""

    stdout: str
    stderr: str
    exit_code: int
    cwd: str
