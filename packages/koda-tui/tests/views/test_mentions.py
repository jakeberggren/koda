"""Tests for @ mentions: which workspace files are suggested, and in what order."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from koda_tui.state import AppState
from koda_tui.views import mentions
from koda_tui.views.mentions import MentionCompleter, ranked, search

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

FILES = ranked([".env", "README.md", "src/app.py", "src/appearance/theme.py"])


def test_visible_shallow_files_are_suggested_first() -> None:
    assert FILES == ["README.md", "src/app.py", "src/appearance/theme.py", ".env"]


def test_path_segment_prefixes_come_before_fuzzy_matches() -> None:
    results = search(FILES, "src/app", limit=10)

    assert results[:2] == ["src/app.py", "src/appearance/theme.py"]
    assert len(results) == len(set(results))


def test_the_limit_and_an_empty_query_are_respected() -> None:
    assert len(search(FILES, "e", limit=2)) == 2
    assert search(FILES, "", limit=10) == []


def test_search_stops_checking_paths_once_it_has_enough(monkeypatch: pytest.MonkeyPatch) -> None:
    checked: list[str] = []
    match = mentions.prefix_match

    def counting(path: str, query: str) -> bool:
        checked.append(path)
        return match(path, query)

    monkeypatch.setattr(mentions, "prefix_match", counting)

    assert search(FILES, "src", limit=1) == ["src/app.py"]
    assert checked == ["README.md", "src/app.py"]  # Not the files after it.


def _suggested(completer: MentionCompleter, text: str) -> list[str]:
    document = Document(text=text, cursor_position=len(text))
    return [c.display_text for c in completer.get_completions(document, CompleteEvent())]


def test_a_new_mention_looks_at_the_files_on_disk_again(tmp_path: Path) -> None:
    (tmp_path / "old.py").write_text("")
    completer = MentionCompleter(AppState(workspace=tmp_path))
    assert _suggested(completer, "@ne") == []

    (tmp_path / "new.py").write_text("")
    assert _suggested(completer, "@ne") == []  # Still the files from when it began.
    _suggested(completer, "@")

    assert _suggested(completer, "@ne") == ["new.py"]
