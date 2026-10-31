"""Tests for the workspace file index and search."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda_tui.workspace import WorkspaceFiles

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for path in [
        "README.md",
        ".env",
        "src/app.py",
        "src/appearance/theme.py",
        "build/output.js",
        "notes.log",
        ".git/config",
        ".DS_Store",
    ]:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("")
    (tmp_path / ".gitignore").write_text("# build artefacts\nbuild/\n*.log\n")
    return tmp_path


def test_index_skips_ignored_and_version_control_files(workspace: Path) -> None:
    assert sorted(WorkspaceFiles(workspace).files) == [
        ".env",
        ".gitignore",
        "README.md",
        "src/app.py",
        "src/appearance/theme.py",
    ]


def test_index_lists_visible_shallow_files_first(workspace: Path) -> None:
    files = WorkspaceFiles(workspace).files
    assert files.index("README.md") < files.index("src/app.py") < files.index(".env")


def test_refresh_picks_up_new_files(workspace: Path) -> None:
    files = WorkspaceFiles(workspace)
    assert "new.py" not in files.files
    (workspace / "new.py").write_text("")
    files.refresh()
    assert "new.py" in files.files


def test_search_ranks_path_segment_prefixes_before_fuzzy_matches(workspace: Path) -> None:
    results = WorkspaceFiles(workspace).search("src/app", limit=10)
    assert results[:2] == ["src/app.py", "src/appearance/theme.py"]
    assert len(results) == len(set(results))


def test_search_respects_the_limit_and_empty_queries(workspace: Path) -> None:
    files = WorkspaceFiles(workspace)
    assert len(files.search("e", limit=2)) == 2
    assert files.search("", limit=10) == []
