"""Status bar component for Koda TUI."""

from pathlib import Path

from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl

from koda_tui.state import AppState, ResponsePhase

_DIVIDER = " · "
_BASE_FOOTER_BINDINGS = [("ctrl+p", "palette")]
_ELLIPSIS = "..."
_MIN_PLAIN_SECTION_PADDING = len(_DIVIDER) + 1


class StatusBarControl(UIControl):
    """Fixed status bar showing model info and status."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def _workspace_path_relative_to_home(self) -> Path:
        """Return the path relative to the repository root."""
        return self._state.workspace_root.relative_to(Path.home())

    def _get_inflight_status(self) -> str:
        if self._state.is_thinking:
            return "thinking"
        if self._state.response_phase is ResponsePhase.RESPONDING:
            return "responding"
        if self._state.response_phase is ResponsePhase.WORKING:
            return "working"
        return "ready"

    def _get_status(self) -> str:
        if self._state.exit_requested:
            return "press ctrl+c again to exit"
        if not self._state.service_status.is_ready:
            return self._state.service_status.summary
        return self._get_inflight_status()

    @staticmethod
    def _format_token_count(value: int | None) -> str | None:
        if value is None:
            return None
        for threshold, suffix in ((1_000_000, "M"), (1_000, "k")):
            if value >= threshold:
                return f"{value / threshold:.1f}".rstrip("0").rstrip(".") + suffix
        return str(value)

    def _get_context_usage_text(self) -> str | None:
        usage = self._state.usage
        if usage is None:
            return None
        context_percentage = usage.context_window_percentage(self._state.context_window)
        if context_percentage is None:
            return None
        return f"ctx {context_percentage}%"

    def _get_io_usage_text(self) -> str | None:
        total_usage = self._state.total_usage
        if total_usage is None:
            return None

        parts: list[str] = []
        if (input_tokens := self._format_token_count(total_usage.input_tokens)) is not None:
            parts.append(f"{input_tokens} in")
        if (output_tokens := self._format_token_count(total_usage.output_tokens)) is not None:
            parts.append(f"{output_tokens} out")
        if not parts:
            return None
        return _DIVIDER.join(parts)

    def _get_usage_text(self) -> str:
        parts: list[str] = []
        if (context_usage := self._get_context_usage_text()) is not None:
            parts.append(context_usage)
        if (io_usage := self._get_io_usage_text()) is not None:
            parts.append(io_usage)
        return _DIVIDER.join(parts)

    def _get_usage_fragments(self) -> tuple[list[tuple[str, str]], str]:
        usage_text = self._get_usage_text()
        if not usage_text:
            return [], ""
        return [("class:status-bar.left", usage_text)], usage_text

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

    def _get_left_segments(self) -> list[tuple[list[tuple[str, str]], str]]:
        path = f" ~/{self._workspace_path_relative_to_home()}"
        segments: list[tuple[list[tuple[str, str]], str]] = [
            ([("class:status-bar.left", path)], path),
        ]

        provider_name = self._state.provider_name
        model_name = self._state.model_name
        if provider_name and model_name:
            provider_model = f"{provider_name}{_DIVIDER}{model_name}"
            segments.append(([("class:status-bar.left", provider_model)], provider_model))

        if self._state.thinking.id != "none":
            thinking_label = self._state.thinking.label.lower()
            segments.append(([("class:status-bar.thinking", thinking_label)], thinking_label))

        usage_fragments, usage_text = self._get_usage_fragments()
        if usage_fragments:
            segments.append((usage_fragments, usage_text))

        return segments

    def _get_right_fragments(self) -> tuple[list[tuple[str, str]], str]:
        status = self._get_status()
        status_text = status + " "
        footer_fragments, footer_text = self._get_footer_fragments()
        status_style = (
            "class:status-bar.warning"
            if not self._state.service_status.is_ready and not self._state.exit_requested
            else "class:status-bar.right"
        )
        return (
            [
                *footer_fragments,
                ("class:status-bar.muted", _DIVIDER),
                (status_style, status_text),
            ],
            f"{footer_text}{_DIVIDER}{status_text}",
        )

    @staticmethod
    def _join_left_segments(
        segments: list[tuple[list[tuple[str, str]], str]],
    ) -> tuple[list[tuple[str, str]], str]:
        fragments: list[tuple[str, str]] = []
        text_parts: list[str] = []

        for index, (segment_fragments, segment_text) in enumerate(segments):
            if index > 0:
                fragments.append(("class:status-bar.muted", _DIVIDER))
                text_parts.append(_DIVIDER)
            fragments.extend(segment_fragments)
            text_parts.append(segment_text)

        return fragments, "".join(text_parts)

    @staticmethod
    def _truncate_fragments(
        fragments: list[tuple[str, str]],
        max_width: int,
    ) -> list[tuple[str, str]]:
        if max_width <= 0:
            return []

        plain_text = "".join(text for _, text in fragments)
        if len(plain_text) <= max_width:
            return fragments

        if max_width <= len(_ELLIPSIS):
            return [("class:status-bar.muted", _ELLIPSIS[:max_width])]

        return [("class:status-bar.left", plain_text[: max_width - len(_ELLIPSIS)] + _ELLIPSIS)]

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002 - unused argument
        """Create the status bar content."""
        right_fragments, right_text = self._get_right_fragments()
        left_segments = self._get_left_segments()
        left_fragments, left_text = self._join_left_segments(left_segments)
        padding = width - len(left_text) - len(right_text)

        if padding >= _MIN_PLAIN_SECTION_PADDING:
            gap_fragments: list[tuple[str, str]] = [("class:status-bar", " " * padding)]
        else:
            available_left_width = max(0, width - len(right_text) - len(_DIVIDER))
            left_fragments = self._truncate_fragments(left_fragments, available_left_width)
            gap_fragments = [("class:status-bar.muted", _DIVIDER)]

        line = FormattedText(
            [
                *left_fragments,
                *gap_fragments,
                *right_fragments,
            ]
        )

        def get_line(i: int) -> FormattedText:
            return line if i == 0 else FormattedText([])

        return UIContent(get_line=get_line, line_count=1)

    def is_focusable(self) -> bool:
        return False
