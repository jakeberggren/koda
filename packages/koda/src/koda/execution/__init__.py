from koda.execution.docker import DockerCommandExecutor
from koda.execution.host import HostCommandExecutor
from koda.execution.models import ExecutionResult
from koda.execution.protocols import CommandExecutor
from koda.execution.seatbelt import SeatbeltCommandExecutor
from koda_common.settings import SettingsManager


def create_command_executor(settings: SettingsManager) -> CommandExecutor:
    """Create the configured command executor for the current settings."""
    if settings.bash_execution_sandbox == "docker":
        return DockerCommandExecutor(settings)
    if settings.bash_execution_sandbox == "seatbelt":
        return SeatbeltCommandExecutor(settings)
    return HostCommandExecutor(settings)


__all__ = [
    "CommandExecutor",
    "DockerCommandExecutor",
    "ExecutionResult",
    "HostCommandExecutor",
    "SeatbeltCommandExecutor",
    "create_command_executor",
]
