"""Editor primitive: a multi-line input that wraps by word and grows with its text."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from prompt_toolkit.application.current import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import BufferControl, Dimension, UIContent, Window
from prompt_toolkit.layout.processors import explode_text_fragments
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.search import SearchState
from wcwidth import wcswidth, wrap

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.document import Document
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable


class Editor:
    """A multi-line input over ``buffer`` that wraps by word and grows with its text,
    from ``min_height`` up to ``max_height`` rows."""

    def __init__(
        self,
        buffer: Buffer,
        *,
        min_height: int = 1,
        max_height: int | None = None,
        style: str = "",
    ) -> None:
        self._control = EditorControl(buffer=buffer)
        self._window = Window(
            self._control,
            height=Dimension(min=min_height, max=max_height),
            dont_extend_height=True,
            wrap_lines=False,
            style=style,
        )

    def __pt_container__(self) -> Window:
        return self._window

    def move_cursor(self, rows: int) -> bool:
        """Move the cursor ``rows`` wrapped rows up (negative) or down; False at the edge."""
        if (info := self._window.render_info) is not None:
            self._control.sync_wrapped_lines(info.window_width)
        return self._control.move_cursor_vertical(rows)


@dataclass(slots=True, frozen=True)
class _WrappedLine:
    """Metadata for one visual wrapped line.

    Attributes:
        row: Source document row this visual line belongs to.
        start: Inclusive source-column start for cursor/source mapping.
        end: Exclusive source-column end for cursor/source mapping and rendering.
        display_start: Inclusive source-column start used for rendering. This can be
            greater than ``start`` when a wrap-boundary separator space should remain
            in the source range but not be displayed as leading whitespace.
        fragments: Prompt-toolkit style/text fragments rendered for this visual line.
    """

    row: int
    start: int
    end: int
    display_start: int
    fragments: tuple[tuple[str, str], ...]


def _char_width(char: str) -> int:
    """Return printable width for a single character."""
    return max(wcswidth(char), 0)


def _text_width(text: str) -> int:
    """Return printable width for a string."""
    return max(wcswidth(text), 0)


def _wrap_line_ranges(text: str, width: int) -> list[tuple[int, int, int]]:
    """Return source and display ranges for wcwidth-aware word wrapping.

    The returned tuples are ``(start, end, display_start)``. ``start`` and
    ``end`` describe the source-text segment used for cursor mapping, while
    ``display_start`` describes where rendering should begin. Keeping these
    separate lets a continuation line retain its leading separator space in the
    source range, but skip rendering that space at the start of the visual line.

    Args:
        text: Source line to wrap. Newline characters should already be split out
            by the caller.
        width: Maximum visual width for each wrapped line.

    Returns:
        A non-empty list of ``(start, end, display_start)`` ranges. Empty input or
        non-positive width returns ``[(0, 0, 0)]`` so callers always have one
        visual line to render.
    """
    if width <= 0:
        return [(0, 0, 0)]
    if not text:
        return [(0, 0, 0)]

    wrapped_lines = wrap(
        text,
        width=width,
        expand_tabs=False,
        replace_whitespace=True,
        drop_whitespace=False,
        break_on_hyphens=False,
    )

    ranges: list[tuple[int, int, int]] = []
    start = 0
    for wrapped_line in wrapped_lines:
        end = start + len(wrapped_line)
        display_start = start
        if start > 0 and wrapped_line.startswith(" "):
            display_start += 1
        ranges.append((start, end, display_start))
        start = end

    return ranges or [(0, 0, 0)]


def _wrap_content_width(width: int) -> int:
    """Reserve one visible cell for the cursor block when possible."""
    return width - 1 if width > 1 else width


class EditorControl(BufferControl):
    """Buffer control with wcwidth-aware word wrapping."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._wrapped_lines: list[_WrappedLine] = []

    def _get_document(self, *, preview_search: bool) -> Document:
        """Return the current document, matching BufferControl behavior."""
        buffer = self.buffer
        search_control = self.search_buffer_control
        preview_now = preview_search or bool(
            self.preview_search()
            and search_control
            and search_control.buffer.text
            and get_app().layout.search_target_buffer_control == self
        )

        if preview_now and search_control is not None:
            ss = self.search_state
            return buffer.document_for_search(
                SearchState(
                    text=search_control.buffer.text,
                    direction=ss.direction,
                    ignore_case=ss.ignore_case,
                )
            )

        return buffer.document

    @staticmethod
    def _cursor_belongs_to_segment(cursor_col: int, start: int, end: int, line_length: int) -> bool:
        """Return whether cursor should render on this visual segment."""
        if cursor_col == line_length:
            return end == line_length
        return start <= cursor_col < end

    def _build_wrapped_lines(
        self,
        document: Document,
        wrap_width: int,
    ) -> tuple[list[_WrappedLine], Point]:
        """Build visual wrapped lines and cursor position for a document.

        Args:
            document: Prompt-toolkit document to render.
            wrap_width: Maximum visual width available for text content.

        Returns:
            A tuple containing the wrapped visual-line metadata and the cursor
            position translated into wrapped visual coordinates.
        """
        wrapped_lines: list[_WrappedLine] = []
        cursor_position = Point(x=0, y=0)
        cursor_row = document.cursor_position_row
        cursor_col = document.cursor_position_col

        for row in range(document.line_count):
            line_text = document.lines[row]
            line_length = len(line_text)
            ranges = _wrap_line_ranges(line_text, wrap_width)

            for start, end, display_start in ranges:
                wrapped_lines.append(
                    _WrappedLine(
                        row=row,
                        start=start,
                        end=end,
                        display_start=display_start,
                        # Reserve one visible cell so prompt_toolkit has a stable
                        # cursor slot at wrapped segment boundaries.
                        fragments=(("", line_text[display_start:end]), ("", " ")),
                    )
                )

                if row == cursor_row and self._cursor_belongs_to_segment(
                    cursor_col,
                    start,
                    end,
                    line_length,
                ):
                    cursor_position = Point(
                        x=_text_width(line_text[display_start:cursor_col]),
                        y=len(wrapped_lines) - 1,
                    )

        return wrapped_lines or [_WrappedLine(0, 0, 0, 0, (("", " "),))], cursor_position

    def _find_wrapped_cursor_position(self, document: Document) -> tuple[int, int] | None:
        """Return the cursor location in wrapped visual coordinates.

        Args:
            document: Current buffer document.

        Returns:
            ``(wrapped_row, display_column)`` when the cursor falls within a known
            wrapped segment; otherwise ``None``.
        """
        cursor_row: int = document.cursor_position_row
        cursor_col: int = document.cursor_position_col
        line_text: str = document.lines[cursor_row]
        for wrapped_index, wrapped in enumerate(self._wrapped_lines):
            if wrapped.row != cursor_row:
                continue
            if not self._cursor_belongs_to_segment(
                cursor_col,
                wrapped.start,
                wrapped.end,
                len(line_text),
            ):
                continue
            return wrapped_index, _text_width(line_text[wrapped.display_start : cursor_col])
        return None

    def move_cursor_vertical(self, direction: int) -> bool:
        """Move the cursor vertically across wrapped visual rows.

        Args:
            direction: Row delta to move. Negative values move up; positive values
                move down.

        Returns:
            ``True`` if the cursor moved to another wrapped row, or ``False`` if
            there was no valid target row.
        """
        document = self.buffer.document
        current = self._find_wrapped_cursor_position(document)
        if current is None:
            return False

        wrapped_index, display_x = current
        target_index = wrapped_index + direction
        if not 0 <= target_index < len(self._wrapped_lines):
            return False

        target = self._wrapped_lines[target_index]
        target_line = document.lines[target.row]
        source_col = self._source_col_from_display_x(
            target_line,
            target.display_start,
            target.end,
            display_x,
        )
        self.buffer.cursor_position = document.translate_row_col_to_index(target.row, source_col)
        return True

    def sync_wrapped_lines(self, width: int) -> None:
        """Refresh cached wrapped-line metadata for the current buffer.

        Args:
            width: Current input window width before reserving the cursor cell.
        """
        wrap_width = max(1, _wrap_content_width(width))
        self._wrapped_lines, _ = self._build_wrapped_lines(self.buffer.document, wrap_width)

    @staticmethod
    def _slice_processed_fragments(
        fragments: StyleAndTextTuples,
        display_start: int,
        end: int,
    ) -> tuple[tuple[str, str], ...]:
        """Slice processed fragments for a wrapped visual segment.

        Args:
            fragments: Fully processed fragments for the source document row.
            display_start: Inclusive source-column start for rendered content.
            end: Exclusive source-column end for rendered content.

        Returns:
            The processed style/text fragments for the visual segment, followed by
            a blank cursor slot fragment.
        """
        exploded = explode_text_fragments(fragments)
        # Keep only the first 2 items (text and style) from each tuple
        sliced = tuple((item[0], item[1]) for item in exploded[display_start:end])
        return (*sliced, ("", " "))

    def _processed_wrapped_lines(
        self,
        document: Document,
        width: int,
        height: int,
        wrapped_lines: list[_WrappedLine],
    ) -> list[_WrappedLine]:
        """Apply prompt-toolkit processors to wrapped visual segments.

        Args:
            document: Prompt-toolkit document used to generate processed lines.
            width: Current input window width.
            height: Current input window height.
            wrapped_lines: Wrapped-line metadata before input processors are applied.

        Returns:
            Wrapped-line metadata with processed style/text fragments attached.
        """
        get_processed_line = self._create_get_processed_line_func(document, width, height)

        return [
            _WrappedLine(
                row=wrapped.row,
                start=wrapped.start,
                end=wrapped.end,
                display_start=wrapped.display_start,
                fragments=self._slice_processed_fragments(
                    get_processed_line(wrapped.row).fragments,
                    wrapped.display_start,
                    wrapped.end,
                ),
            )
            for wrapped in wrapped_lines
        ]

    def _get_menu_position(self, buffer: Buffer) -> Point | None:
        """Return native prompt_toolkit completion menu position, if any."""
        menu_position = self.menu_position() if self.menu_position else None
        if menu_position is not None:
            menu_row, menu_col = buffer.document.translate_index_to_position(menu_position)
            return Point(x=menu_col, y=menu_row)

        if buffer.complete_state:
            menu_row, menu_col = buffer.document.translate_index_to_position(
                min(
                    buffer.cursor_position,
                    buffer.complete_state.original_document.cursor_position,
                )
            )
            return Point(x=menu_col, y=menu_row)

        return None

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int:
        """The number of rows the text takes once wrapped to ``width``."""
        return _wrapped_line_count(self.buffer.text, width)

    @typing.override
    def create_content(
        self,
        width: int,
        height: int,
        preview_search: bool = False,
    ) -> UIContent:
        """Create content with word-wrapped visual lines."""
        buffer = self.buffer
        buffer.load_history_if_not_yet_loaded()
        document = self._get_document(preview_search=preview_search)
        wrap_width = max(1, _wrap_content_width(width))
        self._wrapped_lines, cursor_position = self._build_wrapped_lines(document, wrap_width)
        self._wrapped_lines = self._processed_wrapped_lines(
            document,
            width,
            height,
            self._wrapped_lines,
        )

        def get_line(i: int) -> StyleAndTextTuples:
            if 0 <= i < len(self._wrapped_lines):
                return list(self._wrapped_lines[i].fragments)
            return [("", " ")]

        content = UIContent(
            get_line=get_line,
            line_count=len(self._wrapped_lines),
            cursor_position=cursor_position,
        )

        if get_app().layout.current_control == self:
            content.menu_position = self._get_menu_position(buffer)

        return content

    @staticmethod
    def _source_col_from_display_x(
        line_text: str,
        start: int,
        end: int,
        display_x: int,
    ) -> int:
        """Translate a wrapped segment display x to a source column."""
        source_col = start
        current_width = 0

        while source_col < end:
            char_width = _char_width(line_text[source_col])
            if current_width + char_width > display_x:
                break
            current_width += char_width
            source_col += 1

        return source_col

    def _mouse_index(self, mouse_event: MouseEvent) -> int | None:
        """Return source index for a mouse position on wrapped content."""
        if not (0 <= mouse_event.position.y < len(self._wrapped_lines)):
            return None

        wrapped = self._wrapped_lines[mouse_event.position.y]
        line_text = self.buffer.document.lines[wrapped.row]
        source_col = self._source_col_from_display_x(
            line_text,
            wrapped.display_start,
            wrapped.end,
            mouse_event.position.x,
        )
        return self.buffer.document.translate_row_col_to_index(wrapped.row, source_col)

    def _apply_mouse_index(self, mouse_event: MouseEvent, index: int) -> None:
        """Update the cursor from a resolved mouse index."""
        buffer = self.buffer
        if mouse_event.event_type in {MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP}:
            buffer.cursor_position = index

    def mouse_handler(self, mouse_event: MouseEvent):
        """Translate clicks from visual wrapped lines back to source lines."""

        index = self._mouse_index(mouse_event)
        if index is None:
            return
        self._apply_mouse_index(mouse_event, index)
        return


def _wrapped_line_count(text: str, width: int) -> int:
    """The number of rows ``text`` takes once wrapped to ``width``."""
    if width <= 0:
        return 1
    wrap_width = max(1, _wrap_content_width(width))
    return max(1, sum(len(_wrap_line_ranges(line, wrap_width)) for line in text.split("\n")))
