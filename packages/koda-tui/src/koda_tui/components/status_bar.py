"""Status bar component for Koda TUI."""

from pathlib import Path

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl

from koda_tui.state import AppState, ResponsePhase

_DIVIDER = " · "
_BASE_FOOTER_BINDINGS = [("ctrl+p", "palette")]


class StatusBarControl(UIControl):
    """Fixed status bar showing model info and status."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def _path_relative_to_home(self) -> Path:
        """Return the path relative to the repository root."""
        return self._state.cwd.relative_to(Path.home())

    def _get_status(self) -> str:
        if self._state.exit_requested:
            return "press ctrl+c again to exit"
        if self._state.is_thinking:
            return "thinking"
        if self._state.response_phase is ResponsePhase.RESPONDING:
            return "responding"
        if self._state.response_phase is ResponsePhase.WORKING:
            return "working"
        return "ready"

    def _get_footer_fragments(self) -> tuple[list[tuple[str, str]], str]:
        """Return styled footer binding fragments and their plain-text representation."""
        fragments: list[tuple[str, str]] = []
        text_parts: list[str] = []
        footer_bindings = list(_BASE_FOOTER_BINDINGS)
        if self._state.thinking_supported:
            footer_bindings.insert(0, ("ctrl+t", "thinking"))

        for index, (keybinding, label) in enumerate(footer_bindings):
            if index > 0:
                fragments.append(("class:status-bar.muted", _DIVIDER))
                text_parts.append(_DIVIDER)

            fragments.append(("class:status-bar.keybinding", keybinding))
            fragments.append(("class:status-bar.muted", f" {label}"))
            text_parts.append(f"{keybinding} {label}")

        return fragments, "".join(text_parts)

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002 - unused argument
        """Create the status bar content."""
        # Left side: provider/model info
        path = f" ~/{self._path_relative_to_home()}"
        left_fragments: list[tuple[str, str]] = [
            ("class:status-bar.left", path),
            ("class:status-bar.muted", _DIVIDER),
            (
                "class:status-bar.left",
                f"{self._state.provider_name}{_DIVIDER}{self._state.model_name}",
            ),
        ]
        left_text = f"{path}{_DIVIDER}{self._state.provider_name}{_DIVIDER}{self._state.model_name}"
        if self._state.thinking.id != "none":
            thinking_label = self._state.thinking.label.lower()
            left_fragments.extend(
                [
                    ("class:status-bar.muted", _DIVIDER),
                    ("class:status-bar.thinking", thinking_label),
                ]
            )
            left_text += f"{_DIVIDER}{thinking_label}"

        # Right side: footer help + status
        status = self._get_status()
        footer_fragments, footer_text = self._get_footer_fragments()
        right_text = f"{footer_text}{_DIVIDER}{status}"

        # Calculate padding
        padding = width - len(left_text) - len(right_text) - 2
        padding = max(1, padding)

        line = FormattedText(
            [
                *left_fragments,
                ("class:status-bar", " " * padding),
                *footer_fragments,
                ("class:status-bar.muted", _DIVIDER),
                ("class:status-bar.right", status + " "),
            ]
        )

        def get_line(i: int) -> FormattedText:
            return line if i == 0 else FormattedText([])

        return UIContent(get_line=get_line, line_count=1)

    def is_focusable(self) -> bool:
        return False
