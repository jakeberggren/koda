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
from wcwidth import wcwidth

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.layout import WindowRenderInfo

    from koda_tui.app.state import AppState
    from koda_tui.rendering import RichToPromptToolkit


class _LineBuilder:
    """Helper to build wrapped lines from formatted text."""

    def __init__(self, width: int) -> None:
        self.width = width
        self.lines: list[list[tuple[str, str]]] = []
        self.current_line: list[tuple[str, str]] = []
        self.current_width = 0

    def finish_line(self) -> None:
        """Complete the current line and start a new one."""
        self.lines.append(self.current_line)
        self.current_line = []
        self.current_width = 0

    def add_char(self, style: str, char: str) -> None:
        """Add a character, wrapping to new line if needed."""
        char_width = wcwidth(char)
        if char_width < 0:
            # Non-printable, include but don't count width
            self.current_line.append((style, char))
        elif self.current_width + char_width > self.width:
            self.finish_line()
            self.current_line = [(style, char)]
            self.current_width = char_width
        else:
            self.current_line.append((style, char))
            self.current_width += char_width

    def build(self) -> list[FormattedText]:
        """Return the completed list of lines."""
        if self.current_line:
            self.lines.append(self.current_line)
        return [FormattedText(line) for line in self.lines] or [FormattedText([])]


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

    def _render_fragments(self) -> list[FormattedText]:
        """Render all messages and streaming content into fragments."""
        fragments: list[FormattedText] = []

        for message in self._state.messages:
            fragments.append(self._renderer.render_message(message))
            fragments.append(FormattedText([("", "\n")]))

        if self._state.is_streaming and self._state.current_streaming_content:
            fragments.append(
                self._renderer.render_streaming_content(self._state.current_streaming_content)
            )
        elif self._state.is_streaming:
            fragments.append(self._renderer.render_thinking_spinner())

        return fragments

    def _split_into_lines(self, text: FormattedText, width: int) -> list[FormattedText]:
        """Split formatted text into lines respecting width."""
        builder = _LineBuilder(width)
        for fragment in text:
            style, content = fragment[0], fragment[1]
            for char in content:
                if char == "\n":
                    builder.finish_line()
                else:
                    builder.add_char(style, char)
        return builder.build()

    def _merge_and_split(self, fragments: list[FormattedText], width: int) -> list[FormattedText]:
        """Merge fragments and split into wrapped lines."""
        if not fragments:
            return [FormattedText([])]
        merged = to_formatted_text(merge_formatted_text(fragments))
        return self._split_into_lines(merged, width)

    def _is_at_bottom(self, height: int) -> bool:
        """Check if scroll is at or near the bottom."""
        max_offset = max(0, self._total_lines - height)
        return self._scroll_offset >= max_offset

    def _update_scroll(self, height: int, *, is_at_bottom: bool) -> None:
        """Update scroll offset with auto-scroll and clamping."""
        max_offset = max(0, self._total_lines - height)

        if is_at_bottom:
            self._scroll_offset = max_offset
        else:
            self._scroll_offset = min(self._scroll_offset, max_offset)

    def _build_ui_content(self, height: int) -> UIContent:
        """Build the final UIContent with line getter and cursor."""
        cursor_y = min(self._scroll_offset + height - 1, self._total_lines - 1)

        def get_line(i: int) -> FormattedText:
            actual_line = i + self._scroll_offset
            if 0 <= actual_line < self._total_lines:
                return self._lines[actual_line]
            return FormattedText([])

        return UIContent(
            get_line=get_line,
            line_count=min(height, max(self._total_lines, 1)),
            cursor_position=Point(x=0, y=max(0, cursor_y)),
        )

    def scroll_up(self, scroll_amount: int = 1) -> None:
        """Scroll up by given amount."""
        self._scroll_offset = max(0, self._scroll_offset - scroll_amount)

    def scroll_down(self, scroll_amount: int = 1) -> None:
        """Scroll down by given amount."""
        max_offset = max(0, self._total_lines - self._view_height)
        self._scroll_offset = min(self._scroll_offset + scroll_amount, max_offset)

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse scroll events."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll_up()
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll_down()

    def create_content(self, width: int, height: int) -> UIContent:
        """Create the content for the chat area."""
        self._view_height = height
        self._renderer.set_width(width)

        # Check if at bottom BEFORE content changes
        at_bottom = self._is_at_bottom(height)

        fragments = self._render_fragments()
        self._lines = self._merge_and_split(fragments, width)
        self._total_lines = len(self._lines)
        self._update_scroll(height, is_at_bottom=at_bottom)

        return self._build_ui_content(height)


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
