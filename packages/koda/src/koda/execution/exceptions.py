class CommandExecutionError(Exception):
    """Error launching or configuring command execution."""

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(str(cause))


class CommandTimeoutError(Exception):
    """Command execution timed out."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        super().__init__(f"Command timed out after {timeout} seconds")
