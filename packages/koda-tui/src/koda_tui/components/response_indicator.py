"""Bottom-docked response indicator for in-flight agent work."""

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.layout import UIContent, UIControl

from koda_tui.rendering import MessageRenderer
from koda_tui.state import AppState


class ResponseIndicatorControl(UIControl):
    """Single-line response indicator shown above the input area."""

    def __init__(self, state: AppState, renderer: MessageRenderer) -> None:
        self._state = state
        self._renderer = renderer

    @staticmethod
    def _get_text() -> str:
        return "Working... (esc to interrupt)"

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        """Create the response indicator content."""
        line = to_formatted_text(
            self._renderer.render_thinking_spinner(self._get_text()),
            auto_convert=True,
        )

        def get_line(i: int) -> FormattedText:
            return line if i == 0 else FormattedText([])

        return UIContent(get_line=get_line, line_count=1)

    def is_focusable(self) -> bool:
        return False
