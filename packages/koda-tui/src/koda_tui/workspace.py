"""The workspace: an index of its files, and search over them."""

from __future__ import annotations

import os
from itertools import chain, islice
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec
from prompt_toolkit.completion import CompleteEvent, Completer, Completion, FuzzyCompleter
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

IGNORE_FILENAMES = (".gitignore", ".ignore")
EXCLUDED_DIRS = frozenset({".git", ".hg", ".svn"})
EXCLUDED_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


class WorkspaceFiles:
    """The workspace's files, as paths relative to its root, and search over them.

    The index is built on first use and rebuilt by ``refresh``. Files excluded by the
    workspace's ignore files, and version-control directories, are left out.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._ignore = IgnoreRules(root)
        self._files: list[str] | None = None
        self._fuzzy = FuzzyCompleter(PathCompleter(lambda: self.files))

    @property
    def files(self) -> list[str]:
        """The indexed paths, building the index if needed."""
        if self._files is None:
            self.refresh()
        return self._files or []

    def refresh(self) -> None:
        """Rebuild the index from the files on disk."""
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            current_dir = Path(dirpath)
            dirnames[:] = sorted(
                dirname
                for dirname in dirnames
                if dirname not in EXCLUDED_DIRS
                and not self._ignore.matches(current_dir / dirname, is_dir=True)
            )
            for filename in sorted(filenames):
                candidate = current_dir / filename
                if filename in EXCLUDED_FILES or self._ignore.matches(candidate):
                    continue
                files.append(candidate.relative_to(self._root).as_posix())
        self._files = sorted(files, key=_sort_key)

    def search(self, query: str, limit: int) -> list[str]:
        """Up to ``limit`` paths matching ``query``: path-segment prefix matches first,
        then fuzzy matches."""
        if not query:
            return []
        matches = chain(self._prefix_matches(query), self._fuzzy_matches(query))
        return list(islice(_unique(matches), limit))

    def _prefix_matches(self, query: str) -> list[str]:
        return [path for path in self.files if _path_segment_prefix_match(path, query)]

    def _fuzzy_matches(self, query: str) -> Iterator[str]:
        completions = self._fuzzy.get_completions(
            Document(text=query, cursor_position=len(query)),
            CompleteEvent(text_inserted=True),
        )
        return (completion.text for completion in completions)


class IgnoreRules:
    """Matches workspace paths against the workspace's ignore files."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._spec = _read_spec(root)

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


class PathCompleter(Completer):
    """Completes full workspace-relative paths, for fuzzy matching."""

    def __init__(self, get_paths: Callable[[], list[str]]) -> None:
        self._get_paths = get_paths

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002
    ) -> Iterator[Completion]:
        text = document.text
        for path in self._get_paths():
            yield Completion(path, start_position=-len(text))


def _read_spec(root: Path) -> pathspec.PathSpec | None:
    """A pathspec from the supported ignore files in ``root``, if they have patterns."""
    patterns: list[str] = []
    for filename in IGNORE_FILENAMES:
        ignore_path = root / filename
        if not ignore_path.is_file():
            continue
        try:
            lines = ignore_path.read_text().splitlines()
        except OSError:
            continue
        patterns.extend(line for line in lines if line.strip() and not line.strip().startswith("#"))
    if not patterns:
        return None
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def _sort_key(path: str) -> tuple[int, int, int, str]:
    """Prefer visible, shallow paths, then sort by file name."""
    parts = Path(path).parts
    depth = len(parts)
    basename = parts[-1] if parts else path
    has_dot_part = any(part.startswith(".") for part in parts)
    return (has_dot_part, depth > 1, depth, basename.casefold())


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


def _unique(paths: Iterable[str]) -> Iterator[str]:
    """``paths`` in order, each only the first time it appears."""
    seen: set[str] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            yield path
