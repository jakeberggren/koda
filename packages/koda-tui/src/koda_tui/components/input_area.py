"""Input area component for Koda TUI."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import BufferControl, Window
from prompt_toolkit.layout.dimension import Dimension
from wcwidth import wcswidth

if TYPE_CHECKING:
    from koda_tui.state import AppState


class InputArea:
    """Dynamic-height input area that grows with content."""

    # Account for prompt (2) and scrollbar (1)
    DEFAULT_WIDTH_OFFSET = 3
    MIN_HEIGHT = 1
    MAX_HEIGHT = 10

    def __init__(self, state: AppState) -> None:
        self._state = state
        self.buffer = Buffer(
            multiline=True,
            name="input_buffer",
        )
        self._control = BufferControl(buffer=self.buffer)

    def _count_wrapped_lines(self, text: str, width: int) -> int:
        """Count visual lines after wrapping."""
        if width <= 0:
            return 1

        line_count = 0
        for line in text.split("\n"):
            if not line:
                line_count += 1
                continue

            line_width = wcswidth(line)
            if line_width <= 0:
                line_count += 1
            else:
                # Ceiling division to count wrapped lines
                line_count += (line_width + width - 1) // width

        return max(1, line_count)

    def get_height(self) -> Dimension:
        """Calculate height based on wrapped line count."""
        width_offset = self.DEFAULT_WIDTH_OFFSET if self._state.show_scrollbar else 2
        terminal_width = shutil.get_terminal_size().columns - width_offset
        line_count = self._count_wrapped_lines(self.buffer.text, terminal_width)
        height = max(self.MIN_HEIGHT, min(line_count, self.MAX_HEIGHT))
        return Dimension(min=self.MIN_HEIGHT, max=self.MAX_HEIGHT, preferred=height)

    def create_window(self) -> Window:
        """Create the input window with buffer control."""
        return Window(
            content=self._control,
            height=self.get_height,
            wrap_lines=True,
            dont_extend_height=True,
        )

    def get_text(self) -> str:
        """Get current input text."""
        return self.buffer.text

    def clear(self) -> None:
        """Clear the input buffer."""
        self.buffer.reset()

    @property
    def control(self) -> BufferControl:
        """Get the buffer control for focus management."""
        return self._control
