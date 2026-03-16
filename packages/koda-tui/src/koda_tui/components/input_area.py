"""Input area component for Koda TUI."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    FuzzyCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.layout import BufferControl, UIContent, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import Margin
from wcwidth import wcswidth

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
        self._ignore_matcher = _IgnoreMatcher(state.cwd)
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
        self._control = BufferControl(buffer=self.buffer)

    def _count_wrapped_lines(self, text: str, width: int) -> int:
        """Count visual lines after wrapping."""
        if width <= 0:
            return 1

        line_count = 0
        for line in text.split("\n"):
            if not line:
                line_count += 1
                continue

            line_width = wcswidth(line)
            if line_width <= 0:
                line_count += 1
            else:
                # Ceiling division to count wrapped lines
                line_count += (line_width + width - 1) // width

        return max(1, line_count)

    def _get_input_width(self) -> int:
        """Return current input content width (without margins)."""
        if self._window and self._window.render_info is not None:
            return max(1, self._window.render_info.window_width)

        width_offset = self.DEFAULT_WIDTH_OFFSET if self._state.show_scrollbar else 2
        return max(1, shutil.get_terminal_size().columns - width_offset)

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
        root = self._state.cwd
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
            wrap_lines=True,
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
        replacement = f"@{selected}{suffix}"
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
