"""@ mentions: the workspace files to suggest for the mention being typed."""

from __future__ import annotations

from itertools import chain, islice
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.completion import CompleteEvent, Completer, Completion, FuzzyCompleter
from prompt_toolkit.document import Document

from koda import harness

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from koda_tui.state import AppState

SUGGESTIONS = 10  # Most files suggested for an @ mention.


class MentionCompleter(Completer):
    """Workspace files for the @ mention before the cursor; each puts its path after
    the ``@``, then a space, so the cursor leaves the mention. A new mention, just
    ``@``, looks at the files on disk again."""

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._files: list[str] | None = None

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002 - completes the same however asked
    ) -> Iterator[Completion]:
        if (query := mention(document)) is None:
            return
        if not query or self._files is None:
            self._files = ranked(harness.Workspace(self._state.workspace).files())
        for path in search(self._files, query, SUGGESTIONS):
            yield Completion(f"{path} ", start_position=-len(query), display=path)


def mention(document: Document) -> str | None:
    """What is typed after the ``@`` of the mention before the cursor, if it's in one."""
    word = document.get_word_before_cursor(WORD=True)
    return word[1:] if word.startswith("@") else None


def ranked(files: list[str]) -> list[str]:
    """``files`` in the order to suggest them: visible, shallow paths first, then by name."""
    return sorted(files, key=rank)


def rank(path: str) -> tuple[bool, bool, int, str]:
    parts = Path(path).parts
    hidden = any(part.startswith(".") for part in parts)
    return (hidden, len(parts) > 1, len(parts), parts[-1].casefold())


def search(files: list[str], query: str, limit: int) -> list[str]:
    """Up to ``limit`` of ``files`` matching ``query``, in their order: path-segment
    prefix matches first, then fuzzy matches."""
    if not query:
        return []
    prefixed = (path for path in files if prefix_match(path, query))
    fuzzy = FuzzyCompleter(PathCompleter(files)).get_completions(
        Document(text=query, cursor_position=len(query)),
        CompleteEvent(text_inserted=True),
    )
    return list(islice(unique(chain(prefixed, (c.text for c in fuzzy))), limit))


def prefix_match(path: str, query: str) -> bool:
    """Whether the segments of ``query`` begin consecutive segments of ``path``."""
    query_parts = [part.casefold() for part in query.split("/") if part]
    path_parts = [part.casefold() for part in Path(path).parts]
    size = len(query_parts)
    if not query_parts or size > len(path_parts):
        return False
    windows = (path_parts[start : start + size] for start in range(len(path_parts) - size + 1))
    return any(
        all(part.startswith(prefix) for part, prefix in zip(window, query_parts, strict=True))
        for window in windows
    )


def unique(paths: Iterable[str]) -> Iterator[str]:
    """``paths`` in order, each only the first time it appears."""
    seen: set[str] = set()
    for path in paths:
        if path not in seen:
            seen.add(path)
            yield path


class PathCompleter(Completer):
    """Completes whole paths from ``files``, for fuzzy matching."""

    def __init__(self, files: list[str]) -> None:
        self._files = files

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,  # noqa: ARG002 - completes the same however asked
    ) -> Iterator[Completion]:
        for path in self._files:
            yield Completion(path, start_position=-len(document.text))
