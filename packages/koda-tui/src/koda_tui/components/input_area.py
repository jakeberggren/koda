"""Input area component for Koda TUI."""

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import BufferControl, Window
from prompt_toolkit.layout.dimension import Dimension


class InputArea:
    """Dynamic-height input area that grows with content."""

    MIN_HEIGHT = 1
    MAX_HEIGHT = 10

    def __init__(self) -> None:
        self.buffer = Buffer(
            multiline=True,
            name="input_buffer",
        )
        self._control = BufferControl(buffer=self.buffer)

    def get_height(self) -> Dimension:
        """Calculate height based on content."""
        line_count = self.buffer.document.line_count
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
