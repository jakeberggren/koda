"""Chat area component for Koda TUI."""

from prompt_toolkit.formatted_text import FormattedText, merge_formatted_text, to_formatted_text
from prompt_toolkit.layout import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from koda_tui.app.state import AppState
from koda_tui.rendering import RichToPromptToolkit


class ChatAreaControl(UIControl):
    """Scrollable chat history control."""

    def __init__(self, state: AppState, renderer: RichToPromptToolkit) -> None:
        self._state = state
        self._renderer = renderer
        self._scroll_offset = 0
        self._total_lines = 0
        self._view_height = 0

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: C901 - complexity
        """Create the content for the chat area."""
        # Update renderer width for proper wrapping
        self._renderer.set_width(width)

        # Render all messages
        fragments: list[FormattedText] = []

        for message in self._state.messages:
            rendered = self._renderer.render_message(message)
            fragments.append(rendered)
            fragments.append(FormattedText([("", "\n\n")]))

        # Add streaming content if active
        if self._state.is_streaming and self._state.current_streaming_content:
            streaming = self._renderer.render_streaming_content(
                self._state.current_streaming_content
            )
            fragments.append(streaming)
        elif self._state.is_streaming:
            spinner = self._renderer.render_thinking_spinner()
            fragments.append(spinner)

        # Add active tool spinner
        if self._state.active_tool:
            spinner = self._renderer.render_tool_spinner(self._state.active_tool.tool_name)
            fragments.append(FormattedText([("", "\n")]))
            fragments.append(spinner)

        # Merge fragments and convert to list of tuples
        if fragments:
            merged = to_formatted_text(merge_formatted_text(fragments))
        else:
            merged = FormattedText([])

        # Split into lines for UIContent
        lines = self._split_into_lines(merged, width)
        line_count = len(lines)

        # Store for scroll bounds checking
        self._total_lines = line_count
        self._view_height = height

        # Auto-scroll to bottom when streaming or new content
        if self._state.is_streaming or self._state.active_tool:
            self._scroll_offset = max(0, line_count - height)

        def get_line(i: int) -> FormattedText:
            actual_line = i + self._scroll_offset
            if 0 <= actual_line < len(lines):
                return lines[actual_line]
            return FormattedText([])

        return UIContent(
            get_line=get_line,
            line_count=max(line_count - self._scroll_offset, height),
            cursor_position=None,
        )

    def _split_into_lines(self, text: FormattedText, width: int) -> list[FormattedText]:  # noqa: C901 - complexity
        """Split formatted text into lines respecting width."""
        lines: list[list[tuple[str, str]]] = []
        current_line: list[tuple[str, str]] = []
        current_width = 0

        for fragment in text:
            style, content = fragment[0], fragment[1]
            for char in content:
                if char == "\n":
                    lines.append(current_line)
                    current_line = []
                    current_width = 0
                elif current_width >= width:
                    lines.append(current_line)
                    current_line = [(style, char)]
                    current_width = 1
                else:
                    current_line.append((style, char))
                    current_width += 1

        if current_line:
            lines.append(current_line)

        return [FormattedText(line) for line in lines] or [FormattedText([])]

    def scroll_up(self, lines: int = 5) -> None:
        """Scroll up by the specified number of lines."""
        self._scroll_offset = max(0, self._scroll_offset - lines)

    def scroll_down(self, lines: int = 5) -> None:
        """Scroll down by the specified number of lines."""
        max_offset = max(0, self._total_lines - self._view_height)
        self._scroll_offset = min(self._scroll_offset + lines, max_offset)

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse scroll events."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll_up(3)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll_down(3)

    def is_focusable(self) -> bool:
        return True
