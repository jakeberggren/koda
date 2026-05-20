class AgentConfigError(Exception):
    """Raised when agent config is invalid."""

    def __init__(self, field_name: str, value: object, expected: str) -> None:
        self.field_name = field_name
        self.value = value
        self.expected = expected
        super().__init__(f"Invalid `{field_name}`: expected {expected}, got {value}.")
