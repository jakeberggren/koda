"""Editor primitive: a multi-line input that wraps by word and grows with its text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import BufferControl, Dimension, UIContent, Window
from prompt_toolkit.layout.processors import explode_text_fragments
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.utils import get_cwidth
from wcwidth import wrap

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.document import Document
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding.key_bindings import NotImplementedOrNone
    from prompt_toolkit.layout.containers import GetLinePrefixCallable

CURSOR_SLOT: tuple[str, str] = ("", " ")  # Ends each row, so the cursor has a cell there.


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
        self._control = EditorControl(buffer)
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
            self._control.rewrap(info.window_width)
        return self._control.move_cursor_vertical(rows)


@dataclass(frozen=True, slots=True)
class _Row:
    """One drawn row: part of ``line`` of the text. The cursor can be from ``start`` to
    ``end``; drawing begins at ``shown``, past a space the wrap left at the row's start."""

    line: int
    start: int
    end: int
    shown: int


class EditorControl(BufferControl):
    """A BufferControl that wraps by word, measuring cells, with a cell kept free at
    the end of each row for the cursor."""

    def __init__(self, buffer: Buffer) -> None:
        super().__init__(buffer=buffer)
        self._rows: list[_Row] = []

    def rewrap(self, width: int) -> None:
        """Wrap the text at ``width`` again, as it may have changed since it was drawn."""
        self._rows = _rows(self.buffer.document, width)

    def move_cursor_vertical(self, rows: int) -> bool:
        """Move the cursor ``rows`` wrapped rows up (negative) or down, keeping its
        column; False if there is no such row."""
        document = self.buffer.document
        if (cursor := self._cursor(document)) is None:
            return False
        index = cursor.y + rows
        if not 0 <= index < len(self._rows):
            return False
        row = self._rows[index]
        column = _column_at(document.lines[row.line], row, cursor.x)
        self.buffer.cursor_position = document.translate_row_col_to_index(row.line, column)
        return True

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int:
        """The number of rows the text takes once wrapped to ``width``."""
        return 1 if width <= 0 else len(_rows(self.buffer.document, width))

    @override
    def create_content(
        self,
        width: int,
        height: int,
        preview_search: bool = False,
    ) -> UIContent:
        """The wrapped rows, drawn with the buffer's processors, such as the selection."""
        self.buffer.load_history_if_not_yet_loaded()
        document = self.buffer.document
        rows = self._rows = _rows(document, width)
        processed = self._create_get_processed_line_func(document, width, height)

        def get_line(index: int) -> StyleAndTextTuples:
            if not 0 <= index < len(rows):
                return [CURSOR_SLOT]
            row = rows[index]
            fragments = explode_text_fragments(processed(row.line).fragments)[row.shown : row.end]
            return [*((style, text) for style, text, *_ in fragments), CURSOR_SLOT]

        return UIContent(
            get_line=get_line,
            line_count=len(rows),
            cursor_position=self._cursor(document) or Point(x=0, y=0),
        )

    @override
    def mouse_handler(self, mouse_event: MouseEvent) -> NotImplementedOrNone:
        """Put the cursor where a click lands on the wrapped rows."""
        x, y = mouse_event.position
        clicked = mouse_event.event_type in {MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP}
        if clicked and 0 <= y < len(self._rows):
            row = self._rows[y]
            document = self.buffer.document
            column = _column_at(document.lines[row.line], row, x)
            self.buffer.cursor_position = document.translate_row_col_to_index(row.line, column)
        return None

    def _cursor(self, document: Document) -> Point | None:
        """The cursor as a wrapped row and a cell in it, if a row holds it."""
        line, column = document.cursor_position_row, document.cursor_position_col
        text = document.lines[line]
        for index, row in enumerate(self._rows):
            if row.line == line and _holds(row, column, len(text)):
                return Point(x=get_cwidth(text[row.shown : column]), y=index)
        return None


def _rows(document: Document, width: int) -> list[_Row]:
    """The document's lines wrapped at ``width``, less the cell kept for the cursor."""
    room = max(1, width - 1 if width > 1 else width)
    return [
        _Row(line, start, end, shown)
        for line, text in enumerate(document.lines)
        for start, end, shown in _wrap_line_ranges(text, room)
    ]


def _wrap_line_ranges(text: str, width: int) -> list[tuple[int, int, int]]:
    """``text``, one line, wrapped by word at ``width`` cells, as ``(start, end, shown)``
    for each row: always at least one row.

    A space the wrap leaves at the start of a row stays in the row's range, so the
    cursor can be on it, but isn't drawn: ``shown`` begins after it.
    """
    if width <= 0 or not text:
        return [(0, 0, 0)]
    ranges: list[tuple[int, int, int]] = []
    start = 0
    for row in wrap(
        text,
        width=width,
        expand_tabs=False,
        replace_whitespace=True,
        drop_whitespace=False,
        break_on_hyphens=False,
    ):
        end = start + len(row)
        ranges.append((start, end, start + 1 if start > 0 and row.startswith(" ") else start))
        start = end
    return ranges or [(0, 0, 0)]


def _holds(row: _Row, column: int, length: int) -> bool:
    """Whether the cursor at ``column`` of a line ``length`` long is on ``row``: the
    end of the line belongs to its last row."""
    return row.end == length if column == length else row.start <= column < row.end


def _column_at(text: str, row: _Row, x: int) -> int:
    """The column of ``text`` drawn at cell ``x`` of ``row``."""
    column, used = row.shown, 0
    while column < row.end and used + get_cwidth(text[column]) <= x:
        used += get_cwidth(text[column])
        column += 1
    return column
