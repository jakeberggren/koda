from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Command:
    """A command that can be executed from the palette."""

    label: str
    handler: Callable[[], None]
    description: str = ""
