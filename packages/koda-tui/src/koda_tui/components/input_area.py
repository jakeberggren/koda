"""Input area component for Koda TUI."""

from __future__ import annotations

import os
import shutil
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    FuzzyCompleter,
)
from prompt_toolkit.data_structures import Point
from prompt_toolkit.document import Document
from prompt_toolkit.layout import BufferControl, UIContent, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import Margin
from prompt_toolkit.layout.processors import explode_text_fragments
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.search import SearchState
from wcwidth import wcswidth, wrap

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import WindowRenderInfo

    from koda_tui.state import AppState

IGNORE_FILENAMES = (".gitignore", ".ignore")


class _IgnoreMatcher:
    """Matches workspace paths against local ignore files."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._spec = self._create_spec(root)

    @staticmethod
    def _create_spec(root: Path) -> pathspec.PathSpec | None:
        """Create a pathspec from supported ignore files."""
        patterns: list[str] = []

        for filename in IGNORE_FILENAMES:
            ignore_path = root / filename
            if not ignore_path.is_file():
                continue

            try:
                lines = ignore_path.read_text().splitlines()
            except OSError:
                continue

            patterns.extend(
                line for line in lines if line.strip() and not line.strip().startswith("#")
            )

        if not patterns:
            return None
        return pathspec.PathSpec.from_lines("gitignore", patterns)

    def matches(self, path: Path, *, is_dir: bool = False) -> bool:
        """Return whether the path matches the ignore spec."""
        if self._spec is None:
            return False

        try:
            relative_path = path.relative_to(self._root)
        except ValueError:
            return False

        match_path = str(relative_path)
        if is_dir:
            match_path = f"{match_path}/"

        return self._spec.match_file(match_path)


class _PromptMargin(Margin):
    """Renders the prompt character on every visible line."""

    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:  # noqa: ARG002
        return 2

    def create_margin(
        self,
        window_render_info: WindowRenderInfo,
        width: int,  # noqa: ARG002
        height: int,  # noqa: ARG002
    ) -> StyleAndTextTuples:
        fragments = []
        fragments.extend(("class:prompt", "▌\n") for _ in range(window_render_info.window_height))
        return fragments


class _WorkspaceFileCompleter(Completer):
    """Complete full workspace-relative file paths."""

    def __init__(self, get_paths: Callable[[], list[str]]) -> None:
        self._get_paths = get_paths

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002
    ):
        text = document.text
        for path in self._get_paths():
            yield Completion(path, start_position=-len(text))


@dataclass(slots=True, frozen=True)
class _WrappedLine:
    """Metadata for one visual wrapped line."""

    row: int
    start: int
    end: int
    fragments: tuple[tuple[str, str], ...]


def _char_width(char: str) -> int:
    """Return printable width for a single character."""
    return max(wcswidth(char), 0)


def _text_width(text: str) -> int:
    """Return printable width for a string."""
    return max(wcswidth(text), 0)


def _wrap_line_ranges(text: str, width: int) -> list[tuple[int, int]]:
    """Return source index ranges for visual word-wrapped lines."""
    if width <= 0:
        return [(0, 0)]
    if not text:
        return [(0, 0)]

    wrapped_lines = wrap(
        text,
        width=width,
        expand_tabs=False,
        replace_whitespace=False,
        drop_whitespace=False,
        break_on_hyphens=False,
    )

    ranges: list[tuple[int, int]] = []
    start = 0
    for wrapped_line in wrapped_lines:
        end = start + len(wrapped_line)
        ranges.append((start, end))
        start = end

    return ranges or [(0, 0)]


def _wrap_content_width(width: int) -> int:
    """Reserve one visible cell for the cursor block when possible."""
    return width - 1 if width > 1 else width


class _WordWrapBufferControl(BufferControl):
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
        """Build wrapped content rows and the corresponding cursor position."""
        wrapped_lines: list[_WrappedLine] = []
        cursor_position = Point(x=0, y=0)
        cursor_row = document.cursor_position_row
        cursor_col = document.cursor_position_col

        for row in range(document.line_count):
            line_text = document.lines[row]
            line_length = len(line_text)
            ranges = _wrap_line_ranges(line_text, wrap_width)

            for start, end in ranges:
                wrapped_lines.append(
                    _WrappedLine(
                        row=row,
                        start=start,
                        end=end,
                        # Reserve one visible cell so prompt_toolkit has a stable
                        # cursor slot at wrapped segment boundaries.
                        fragments=(("", line_text[start:end]), ("", " ")),
                    )
                )

                if row == cursor_row and self._cursor_belongs_to_segment(
                    cursor_col,
                    start,
                    end,
                    line_length,
                ):
                    cursor_position = Point(
                        x=_text_width(line_text[start:cursor_col]),
                        y=len(wrapped_lines) - 1,
                    )

        return wrapped_lines or [_WrappedLine(0, 0, 0, (("", " "),))], cursor_position

    def _find_wrapped_cursor_position(self, document: Document) -> tuple[int, int] | None:
        """Return the current visual wrapped row and display column."""
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
            return wrapped_index, _text_width(line_text[wrapped.start : cursor_col])
        return None

    def move_cursor_vertical(self, direction: int) -> bool:
        """Move the cursor by visual wrapped rows."""
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
            target.start,
            target.end,
            display_x,
        )
        self.buffer.cursor_position = document.translate_row_col_to_index(target.row, source_col)
        return True

    def sync_wrapped_lines(self, width: int) -> None:
        """Refresh wrapped line metadata for the current document and width."""
        wrap_width = max(1, _wrap_content_width(width))
        self._wrapped_lines, _ = self._build_wrapped_lines(self.buffer.document, wrap_width)

    @staticmethod
    def _slice_processed_fragments(
        fragments: StyleAndTextTuples,
        start: int,
        end: int,
    ) -> tuple[tuple[str, str], ...]:
        """Slice processed line fragments for one wrapped source segment."""
        exploded = explode_text_fragments(fragments)
        # Keep only the first 2 items (text and style) from each tuple
        sliced = tuple((item[0], item[1]) for item in exploded[start:end])
        return (*sliced, ("", " "))

    def _processed_wrapped_lines(
        self,
        document: Document,
        width: int,
        height: int,
        wrapped_lines: list[_WrappedLine],
    ) -> list[_WrappedLine]:
        """Apply prompt_toolkit's standard processors to wrapped segments."""
        get_processed_line = self._create_get_processed_line_func(document, width, height)

        return [
            _WrappedLine(
                row=wrapped.row,
                start=wrapped.start,
                end=wrapped.end,
                fragments=self._slice_processed_fragments(
                    get_processed_line(wrapped.row).fragments,
                    wrapped.start,
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
            wrapped.start,
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


class InputArea:
    """Dynamic-height input area that grows with content."""

    # Account for prompt (2) and scrollbar (1)
    DEFAULT_WIDTH_OFFSET = 3
    MIN_HEIGHT = 1
    MAX_HEIGHT = 10
    FILE_DISCOVERY_MAX_RESULTS = 10
    _EXCLUDED_DIRS = frozenset({".git", ".hg", ".svn"})
    _EXCLUDED_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._window: Window | None = None
        self._workspace_files: list[str] | None = None
        self._ignore_matcher = _IgnoreMatcher(state.workspace_root)
        self._file_discovery_results: list[str] = []
        self._file_discovery_selected_index = 0
        self._active_file_token_range: tuple[int, int] | None = None
        self._file_completer = FuzzyCompleter(_WorkspaceFileCompleter(self._get_workspace_files))
        self.buffer = Buffer(
            multiline=True,
            name="input_buffer",
            on_text_changed=self._update_file_discovery,
            on_cursor_position_changed=self._update_file_discovery,
        )
        self._control = _WordWrapBufferControl(buffer=self.buffer)

    def _count_wrapped_lines(self, text: str, width: int) -> int:
        """Count visual lines after wrapping."""
        if width <= 0:
            return 1

        wrap_width = max(1, _wrap_content_width(width))
        return max(1, sum(len(_wrap_line_ranges(line, wrap_width)) for line in text.split("\n")))

    def _get_input_width(self) -> int:
        """Return current input content width (without margins)."""
        if self._window and self._window.render_info is not None:
            return max(1, self._window.render_info.window_width)

        width_offset = self.DEFAULT_WIDTH_OFFSET if self._state.show_scrollbar else 2
        return max(1, shutil.get_terminal_size().columns - width_offset)

    def _sync_wrapped_lines(self) -> None:
        """Refresh wrapped line metadata from the current buffer state."""
        self._control.sync_wrapped_lines(self._get_input_width())

    @staticmethod
    def _workspace_file_sort_key(path: str) -> tuple[int, int, int, str]:
        """Sort workspace files to prefer useful, visible paths first."""
        path_obj = Path(path)
        parts = path_obj.parts
        depth = len(parts)
        basename = parts[-1] if parts else path
        has_dot_part = any(part.startswith(".") for part in parts)
        return (has_dot_part, depth > 1, depth, basename.casefold())

    def _refresh_workspace_files(self) -> None:
        """Build the cached list of workspace-relative file paths."""
        root = self._state.workspace_root
        files: list[str] = []

        for dirpath, dirnames, filenames in os.walk(root):
            current_dir = Path(dirpath)
            dirnames[:] = sorted(
                dirname
                for dirname in dirnames
                if dirname not in self._EXCLUDED_DIRS
                and not self._ignore_matcher.matches(current_dir / dirname, is_dir=True)
            )
            for filename in sorted(filenames):
                candidate = current_dir / filename
                if filename in self._EXCLUDED_FILES or self._ignore_matcher.matches(candidate):
                    continue
                relative_path = candidate.relative_to(root)
                files.append(relative_path.as_posix())

        self._workspace_files = sorted(files, key=self._workspace_file_sort_key)

    def _get_workspace_files(self) -> list[str]:
        """Return cached workspace-relative file paths."""
        if self._workspace_files is None:
            self._refresh_workspace_files()
        return self._workspace_files or []

    @staticmethod
    def _get_active_file_token(text: str, cursor_position: int) -> tuple[int, int, str] | None:
        """Return the active @token around the cursor, if any."""
        if not text:
            return None

        start = cursor_position
        while start > 0 and not text[start - 1].isspace():
            start -= 1

        end = cursor_position
        while end < len(text) and not text[end].isspace():
            end += 1

        token = text[start:end]
        if not token.startswith("@"):
            return None

        return start, end, token[1:]

    @staticmethod
    def _path_segment_prefix_match(path: str, query: str) -> bool:
        """Return whether query segments prefix-match consecutive path segments."""
        query_parts = [part.casefold() for part in query.split("/") if part]
        if not query_parts:
            return False

        path_parts = [part.casefold() for part in Path(path).parts]
        if len(query_parts) > len(path_parts):
            return False

        for start_index in range(len(path_parts) - len(query_parts) + 1):
            window = path_parts[start_index : start_index + len(query_parts)]
            if all(
                part.startswith(query_part)
                for part, query_part in zip(window, query_parts, strict=False)
            ):
                return True

        return False

    @staticmethod
    def _append_unique_result(
        results: list[str],
        seen: set[str],
        path: str,
    ) -> bool:
        """Append a unique result and report whether it was added."""
        if path in seen:
            return False
        seen.add(path)
        results.append(path)
        return True

    def _boosted_file_matches(self, workspace_files: list[str], query: str) -> list[str]:
        """Return prefix-boosted matches from workspace files."""
        return [path for path in workspace_files if self._path_segment_prefix_match(path, query)]

    def _merge_file_results(self, boosted_results: list[str], query: str) -> list[str]:
        """Merge boosted and fuzzy results with deduplication and result limits."""
        results: list[str] = []
        seen: set[str] = set()

        for path in boosted_results:
            if (
                self._append_unique_result(results, seen, path)
                and len(results) >= self.FILE_DISCOVERY_MAX_RESULTS
            ):
                return results

        completions = self._file_completer.get_completions(
            Document(text=query, cursor_position=len(query)),
            CompleteEvent(text_inserted=True),
        )

        for completion in completions:
            if (
                self._append_unique_result(results, seen, completion.text)
                and len(results) >= self.FILE_DISCOVERY_MAX_RESULTS
            ):
                break

        return results

    def _search_workspace_files(self, query: str) -> list[str]:
        """Return fuzzy-matched workspace files for the active query."""
        if not query:
            return []

        workspace_files = self._get_workspace_files()
        boosted_results = self._boosted_file_matches(workspace_files, query)
        return self._merge_file_results(boosted_results, query)

    def _update_file_discovery(self, buffer: Buffer) -> None:
        """Update file discovery from the current buffer content and cursor."""
        token = self._get_active_file_token(buffer.text, buffer.cursor_position)
        if token is None:
            self.close_file_discovery()
            return

        if not self.is_file_discovery_open:
            self._refresh_workspace_files()

        start, end, query = token
        results = self._search_workspace_files(query)
        selected_result = self.selected_file_discovery_result

        self._active_file_token_range = (start, end)
        self._file_discovery_results = results[: self.FILE_DISCOVERY_MAX_RESULTS]

        if not self._file_discovery_results:
            self._file_discovery_selected_index = 0
        elif selected_result in self._file_discovery_results:
            self._file_discovery_selected_index = self._file_discovery_results.index(
                selected_result
            )
        else:
            self._file_discovery_selected_index = 0

    def get_height(self) -> Dimension:
        """Calculate height based on wrapped line count."""
        line_count = self._count_wrapped_lines(self.buffer.text, self._get_input_width())
        height = max(self.MIN_HEIGHT, min(line_count, self.MAX_HEIGHT))
        return Dimension(min=self.MIN_HEIGHT, max=self.MAX_HEIGHT, preferred=height)

    def create_window(self) -> Window:
        """Create the input window with buffer control."""
        self._window = Window(
            content=self._control,
            height=self.get_height,
            wrap_lines=False,
            dont_extend_height=True,
            left_margins=[_PromptMargin()],
        )
        return self._window

    def get_text(self) -> str:
        """Get current input text."""
        return self.buffer.text

    def clear(self) -> None:
        """Clear the input buffer."""
        self.buffer.reset()

    def move_cursor_up(self, count: int = 1) -> None:
        """Move up by wrapped visual rows, falling back to buffer history behavior."""
        for _ in range(count):
            self._sync_wrapped_lines()
            if not self._control.move_cursor_vertical(-1):
                self.buffer.auto_up()

    def move_cursor_down(self, count: int = 1) -> None:
        """Move down by wrapped visual rows, falling back to buffer history behavior."""
        for _ in range(count):
            self._sync_wrapped_lines()
            if not self._control.move_cursor_vertical(1):
                self.buffer.auto_down()

    def move_file_discovery_selection(self, delta: int) -> bool:
        """Move the discovered file selection."""
        if not self.has_file_discovery_selection:
            return False

        self._file_discovery_selected_index = (self._file_discovery_selected_index + delta) % len(
            self._file_discovery_results
        )
        return True

    def close_file_discovery(self) -> bool:
        """Close the discovered files list."""
        was_open = self.is_file_discovery_open
        self._file_discovery_results = []
        self._file_discovery_selected_index = 0
        self._active_file_token_range = None
        return was_open

    def accept_file_discovery_selection(self) -> bool:
        """Replace the active @token with the selected workspace-relative path."""
        selected = self.selected_file_discovery_result
        if selected is None or self._active_file_token_range is None:
            return False

        start, end = self._active_file_token_range
        before = self.buffer.text[:start]
        after = self.buffer.text[end:]
        suffix = "" if not after or after[:1].isspace() else " "
        replacement = f"{selected}{suffix}"
        cursor_position = len(before) + len(replacement)
        self.buffer.set_document(
            Document(text=f"{before}{replacement}{after}", cursor_position=cursor_position),
            bypass_readonly=True,
        )
        self.close_file_discovery()
        return True

    @property
    def file_discovery_results(self) -> list[str]:
        """Return the current discovered file results."""
        return self._file_discovery_results

    @property
    def file_discovery_selected_index(self) -> int:
        """Return the selected discovered file index."""
        return self._file_discovery_selected_index

    @property
    def selected_file_discovery_result(self) -> str | None:
        """Return the selected discovered file path, if any."""
        if not self._file_discovery_results:
            return None
        return self._file_discovery_results[self._file_discovery_selected_index]

    @property
    def has_file_discovery_selection(self) -> bool:
        """Whether file discovery currently has a selectable result."""
        return self.selected_file_discovery_result is not None

    @property
    def is_file_discovery_open(self) -> bool:
        """Whether the discovered file list is currently visible."""
        return self._active_file_token_range is not None
