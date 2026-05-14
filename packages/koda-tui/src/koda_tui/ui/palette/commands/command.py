from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto


class CommandStatus(Enum):
    CONNECTED = auto()
    CURRENT = auto()


@dataclass
class Command:
    """A command that can be executed from the palette."""

    label: str
    handler: Callable[[], None]
    description: str = ""
    group: str | None = None
    status: CommandStatus | None = None
