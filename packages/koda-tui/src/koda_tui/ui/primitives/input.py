"""Input primitive: a single line the user types into."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import BufferControl, Window
from prompt_toolkit.layout.processors import PasswordProcessor

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer


class Input:
    """A single-line input editing ``buffer``; ``masked`` hides what is typed."""

    def __init__(self, buffer: Buffer, *, style: str = "", masked: bool = False) -> None:
        self._window = Window(
            BufferControl(buffer=buffer, input_processors=[PasswordProcessor()] if masked else []),
            style=style,
            height=1,
            dont_extend_height=True,
        )

    def __pt_container__(self) -> Window:
        return self._window
