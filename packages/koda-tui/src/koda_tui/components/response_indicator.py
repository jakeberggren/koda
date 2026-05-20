"""Bottom-docked response indicator for in-flight agent work."""

import time

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl

from koda_tui.state import AppState

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ResponseIndicatorControl(UIControl):
    """Single-line response indicator shown above the input area."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    @staticmethod
    def _get_text() -> str:
        return "Working... (esc to interrupt)"

    @staticmethod
    def _spinner_frame() -> str:
        """Return the current animated spinner frame."""
        frame_index = int(time.time() * 10) % len(_SPINNER_FRAMES)
        return _SPINNER_FRAMES[frame_index]

    def _render_line(self) -> FormattedText:
        """Render the response indicator."""
        spinner = ("class:status-bar.spinner", self._spinner_frame())
        text = ("class:status-bar.muted", f" {self._get_text()}")
        return FormattedText([spinner, text])

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        """Create the response indicator content."""
        line = self._render_line()

        def get_line(i: int) -> FormattedText:
            return line if i == 0 else FormattedText([])

        return UIContent(get_line=get_line, line_count=1)

    def is_focusable(self) -> bool:
        return False
