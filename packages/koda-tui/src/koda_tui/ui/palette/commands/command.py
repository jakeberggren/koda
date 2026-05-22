from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandMarker:
    marker: str
    label_style: str | None = None


@dataclass
class Command:
    """A command that can be executed from the palette."""

    label: str
    handler: Callable[[], None]
    description: str = ""
    group: str | None = None
    marker: CommandMarker | None = None
