"""Chat area component for Koda TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import (
    FormattedText,
    StyleAndTextTuples,
)
from prompt_toolkit.layout import UIContent, UIControl
from prompt_toolkit.layout.margins import Margin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from wcwidth import wcwidth

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.layout import WindowRenderInfo

    from koda_tui.rendering import MessageRenderer
    from koda_tui.state import AppState, Message


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

    def __init__(self, state: AppState, renderer: MessageRenderer) -> None:
        self._state = state
        self._renderer = renderer
        self._lines: list[FormattedText] = []
        self._scroll_offset = 0
        self._total_lines = 0
        self._view_height = 0
        # Pending scroll delta — accumulated between render frames, applied in create_content()
        self._pending_scroll = 0
        # Tracked auto-scroll flag — persists across frames so layout height changes
        # (e.g. queued inputs appearing) don't break auto-scroll.
        self._at_bottom = True
        # Line-level cache invalidation tracking
        self._cached_width = 0
        # Per-message rendering cache: message_id -> (cache_key, FormattedText)
        self._message_cache: dict[int, tuple[tuple, FormattedText]] = {}
        # Per-message wrapped lines cache: message_id -> (cache_key, lines)
        self._lines_cache: dict[int, tuple[tuple, list[FormattedText]]] = {}

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

    def _message_cache_key(self, message: Message) -> tuple:
        """Return cache key for a single message."""
        return (
            message.role,
            message.content,
            message.thinking_content,
            message.tool_call.call_id if message.tool_call else None,
            message.tool_running,
            message.tool_error,
            message.tool_result_display,
            message.tool_error_message,
        )

    def _render_message_cached(self, message: Message) -> FormattedText:
        """Render a message using cache if available."""
        msg_id = id(message)
        cache_key = self._message_cache_key(message)

        cached = self._message_cache.get(msg_id)
        if cached and cached[0] == cache_key:
            return cached[1]

        # Render and cache
        fragment = self._renderer.render_message(message)
        self._message_cache[msg_id] = (cache_key, fragment)
        return fragment

    def _cleanup_caches(self) -> None:
        """Remove cache entries for messages no longer in state."""
        current_ids = {id(m) for m in self._state.messages}
        for cache in (self._message_cache, self._lines_cache):
            stale = [k for k in cache if k not in current_ids]
            for k in stale:
                del cache[k]

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

    def _get_message_lines(self, message: Message, width: int) -> list[FormattedText]:
        """Get wrapped lines for a message, using per-message line cache."""
        msg_id = id(message)
        cache_key = (*self._message_cache_key(message), width)

        cached = self._lines_cache.get(msg_id)
        if cached and cached[0] == cache_key:
            return cached[1]

        fragment = self._render_message_cached(message)
        lines = self._split_into_lines(fragment, width)
        self._lines_cache[msg_id] = (cache_key, lines)
        return lines

    def _rebuild_lines(self, width: int) -> list[FormattedText]:
        """Build all wrapped lines, reusing cached lines for stable messages."""
        self._cleanup_caches()
        all_lines: list[FormattedText] = []

        for message in self._state.messages:
            all_lines.extend(self._get_message_lines(message, width))
            all_lines.append(FormattedText([]))  # blank separator

        if self._state.is_streaming and self._state.current_thinking_content:
            fragment = self._renderer.render_thinking_content(self._state.current_thinking_content)
            all_lines.extend(self._split_into_lines(fragment, width))
            all_lines.append(FormattedText([]))

        if self._state.is_streaming and self._state.current_streaming_content:
            fragment = self._renderer.render_streaming_content(
                self._state.current_streaming_content
            )
            all_lines.extend(self._split_into_lines(fragment, width))
        elif self._state.is_streaming:
            all_lines.extend(
                self._split_into_lines(
                    self._renderer.render_thinking_spinner(),
                    width,
                )
            )

        return all_lines or [FormattedText([])]

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

        self._at_bottom = self._scroll_offset >= max_offset

    def _build_ui_content(self, height: int) -> UIContent:
        """Build the final UIContent with line getter and cursor."""
        cursor_y = min(height - 1, self._total_lines - self._scroll_offset - 1)

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
        self._pending_scroll -= scroll_amount

    def scroll_down(self, scroll_amount: int = 1) -> None:
        """Scroll down by given amount."""
        self._pending_scroll += scroll_amount

    def _apply_pending_scroll(self) -> None:
        """Apply accumulated scroll delta and reset it."""
        if self._pending_scroll == 0:
            return
        max_offset = max(0, self._total_lines - self._view_height)
        self._scroll_offset = max(0, min(self._scroll_offset + self._pending_scroll, max_offset))
        self._pending_scroll = 0
        self._at_bottom = self._scroll_offset >= max_offset

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse scroll events."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll_up()
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll_down()

    def create_content(self, width: int, height: int) -> UIContent:
        """Create the content for the chat area."""
        self._view_height = height

        # Always rebuild lines — per-message caches handle the expensive
        # rendering/wrapping work, so this iteration is cheap.
        if width != self._cached_width:
            self._renderer.set_width(width)
            self._cached_width = width

        self._lines = self._rebuild_lines(width)
        self._total_lines = len(self._lines)
        self._update_scroll(height, is_at_bottom=self._at_bottom)

        # Apply batched scroll events accumulated since last frame
        self._apply_pending_scroll()

        return self._build_ui_content(height)


class ChatScrollbarMargin(Margin):
    """Custom scrollbar that tracks ChatAreaControl's scroll state."""

    SCROLLBAR_CHAR = "█"
    SCROLLBAR_LEFT_PADDING = " "
    SCROLLBAR_TRACK = ("class:scrollbar.track", SCROLLBAR_LEFT_PADDING + SCROLLBAR_CHAR + "\n")
    SCROLLBAR_THUMB = ("class:scrollbar.thumb", SCROLLBAR_LEFT_PADDING + SCROLLBAR_CHAR + "\n")

    def __init__(self, chat_control: ChatAreaControl, state: AppState) -> None:
        self._chat = chat_control
        self._state = state

    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:  # noqa: ARG002
        return 2

    def create_margin(
        self,
        window_render_info: WindowRenderInfo,  # noqa: ARG002
        width: int,  # noqa: ARG002
        height: int,
    ) -> StyleAndTextTuples:
        if not self._state.show_scrollbar:
            return []

        total = self._chat.total_lines
        offset = self._chat.scroll_offset
        view_height = self._chat.view_height

        # Build scrollbar content
        result: StyleAndTextTuples = []

        if total <= view_height or height == 0:  # No scrollbar needed - content fits
            return result
        # Calculate thumb size and position
        thumb_size = max(1, height * view_height // total)
        max_offset = total - view_height
        thumb_pos = (height - thumb_size) * offset // max_offset if max_offset > 0 else 0

        result.extend(
            self.SCROLLBAR_THUMB
            if thumb_pos <= i < thumb_pos + thumb_size
            else self.SCROLLBAR_TRACK
            for i in range(height)
        )

        return result
