"""Status bar component for Koda TUI."""

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl

from koda_tui.app.state import AppState


class StatusBarControl(UIControl):
    """Fixed status bar showing model info and status."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002 - unused argument
        """Create the status bar content."""
        # Left side: provider/model info
        left = f" {self._state.provider_name}/{self._state.model_name}"

        # Right side: status
        if self._state.active_tool:
            status = f"Running: {self._state.active_tool.tool_name}"
        elif self._state.is_streaming:
            status = "Streaming..."
        elif self._state.exit_requested:
            status = "Press Ctrl+C again to exit"
        else:
            status = "Ready"

        # Calculate padding
        padding = width - len(left) - len(status) - 2
        padding = max(1, padding)

        line = FormattedText(
            [
                ("class:status-bar.left", left),
                ("class:status-bar", " " * padding),
                ("class:status-bar.right", status + " "),
            ]
        )

        def get_line(i: int) -> FormattedText:
            return line if i == 0 else FormattedText([])

        return UIContent(get_line=get_line, line_count=1)

    def is_focusable(self) -> bool:
        return False
