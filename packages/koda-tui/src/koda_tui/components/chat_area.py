"""Chat area component for Koda TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import (
    FormattedText,
    StyleAndTextTuples,
    merge_formatted_text,
    to_formatted_text,
)
from prompt_toolkit.layout import UIContent, UIControl
from prompt_toolkit.layout.margins import Margin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.layout import WindowRenderInfo

    from koda_tui.app.state import AppState
    from koda_tui.rendering import RichToPromptToolkit


class ChatAreaControl(UIControl):
    """Scrollable chat history control."""

    def __init__(self, state: AppState, renderer: RichToPromptToolkit) -> None:
        self._state = state
        self._renderer = renderer
        self._lines: list[FormattedText] = []
        self._scroll_offset = 0
        self._total_lines = 0
        self._view_height = 0

    @property
    def total_lines(self) -> int:
        """Total number of lines in the chat content."""
        return self._total_lines

    @property
    def scroll_offset(self) -> int:
        """Current scroll offset from the top."""
        return self._scroll_offset

    @property
    def view_height(self) -> int:
        """Height of the visible viewport."""
        return self._view_height

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: C901 - complexity
        """Create the content for the chat area."""
        self._view_height = height
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

        # Merge fragments and convert to list of tuples
        if fragments:
            merged = to_formatted_text(merge_formatted_text(fragments))
        else:
            merged = FormattedText([])

        # Split into lines for UIContent
        self._lines = self._split_into_lines(merged, width)
        self._total_lines = len(self._lines)

        # Auto-scroll to bottom when streaming
        if self._state.is_streaming or self._state.active_tool:
            self._scroll_offset = max(0, self._total_lines - height)

        # Clamp scroll offset
        max_offset = max(0, self._total_lines - height)
        self._scroll_offset = min(self._scroll_offset, max_offset)

        # Use cursor position to indicate scroll location for scrollbar
        cursor_y = min(self._scroll_offset + height - 1, self._total_lines - 1)
        cursor_pos = Point(x=0, y=max(0, cursor_y))

        def get_line(i: int) -> FormattedText:
            actual_line = i + self._scroll_offset
            if 0 <= actual_line < self._total_lines:
                return self._lines[actual_line]
            return FormattedText([])

        return UIContent(
            get_line=get_line,
            line_count=min(height, max(self._total_lines, 1)),
            cursor_position=cursor_pos,
        )

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse scroll events."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._scroll_offset = max(0, self._scroll_offset - 1)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            max_offset = max(0, self._total_lines - self._view_height)
            self._scroll_offset = min(self._scroll_offset + 1, max_offset)

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


class ChatScrollbarMargin(Margin):
    """Custom scrollbar that tracks ChatAreaControl's scroll state."""

    THUMB_CHAR = "█"
    TRACK_CHAR = "┃"

    def __init__(self, chat_control: ChatAreaControl) -> None:
        self._chat = chat_control

    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:  # noqa: ARG002
        return 1

    def create_margin(
        self,
        window_render_info: WindowRenderInfo,  # noqa: ARG002
        width: int,  # noqa: ARG002
        height: int,
    ) -> StyleAndTextTuples:
        total = self._chat.total_lines
        offset = self._chat.scroll_offset
        view_height = self._chat.view_height

        # Build scrollbar content
        result: StyleAndTextTuples = []

        if total <= view_height or height == 0:
            # No scrollbar needed - content fits
            result.extend([("class:scrollbar.track", self.TRACK_CHAR + "\n")] * height)
        else:
            # Calculate thumb size and position
            thumb_size = max(1, height * view_height // total)
            max_offset = total - view_height
            thumb_pos = (height - thumb_size) * offset // max_offset if max_offset > 0 else 0

            # Build scrollbar
            result.extend(
                ("class:scrollbar.thumb", self.THUMB_CHAR + "\n")
                if thumb_pos <= i < thumb_pos + thumb_size
                else ("class:scrollbar.track", self.TRACK_CHAR + "\n")
                for i in range(height)
            )

        return result
