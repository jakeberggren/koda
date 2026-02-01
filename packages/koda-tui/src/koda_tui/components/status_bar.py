"""Status bar component for Koda TUI."""

from pathlib import Path

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl

from koda_tui.state import AppState


class StatusBarControl(UIControl):
    """Fixed status bar showing model info and status."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def _path_relative_to_home(self) -> Path:
        """Return the path relative to the repository root."""
        return self._state.cwd.relative_to(Path.home())

    def _get_status(self) -> str:
        if self._state.active_tools:
            last_tool = next(reversed(self._state.active_tools.values()))
            return f"Running: {last_tool.tool_name}"
        if self._state.is_streaming:
            return "Streaming"
        if self._state.exit_requested:
            return "Press Ctrl+C again to exit"
        return "Ready"

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002 - unused argument
        """Create the status bar content."""
        # Left side: provider/model info
        path = f" ~/{self._path_relative_to_home()}"
        provider_and_model = f"{self._state.provider_name}/{self._state.model_name}"
        left = f"{path} | {provider_and_model}"

        # Right side: status
        status = self._get_status()

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
