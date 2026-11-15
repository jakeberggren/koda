"""Tool exceptions: what a tool raises when it can't do what was asked. The message goes
back to the model, so it says what went wrong in words the model can act on."""


class ToolError(Exception):
    """Base exception for all tool-related errors."""


class ToolAlreadyRegisteredError(ToolError):
    """Tool is already registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Tool '{name}' is already registered")
