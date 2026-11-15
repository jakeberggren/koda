"""Tests for the workspace: how the tools resolve paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from koda.harness.workspace import NotAFileError, NotAFolderError, PathNotFoundError, Workspace


def test_a_relative_path_is_relative_to_the_root(workspace: Workspace, workspace_dir: Path) -> None:
    assert workspace.resolve("src/a.py") == workspace_dir / "src" / "a.py"


def test_a_path_outside_the_root_is_allowed(workspace: Workspace, workspace_dir: Path) -> None:
    assert workspace.resolve("../elsewhere.txt") == workspace_dir.parent / "elsewhere.txt"


def test_an_absolute_path_stays_as_it_is(workspace: Workspace, tmp_path: Path) -> None:
    assert workspace.resolve(str(tmp_path / "x.txt")) == (tmp_path / "x.txt").resolve()


def test_the_root_is_absolute_with_symlinks_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    monkeypatch.chdir(tmp_path)

    assert Workspace(Path("link")).root == (tmp_path / "real").resolve()


async def test_a_file_is_found(workspace: Workspace, workspace_dir: Path) -> None:
    (workspace_dir / "a.txt").write_text("a", encoding="utf-8")

    assert await workspace.file("a.txt") == workspace_dir / "a.txt"
    assert await workspace.existing("a.txt") == workspace_dir / "a.txt"


async def test_a_folder_is_found(workspace: Workspace, workspace_dir: Path) -> None:
    (workspace_dir / "src").mkdir()

    assert await workspace.folder("src") == workspace_dir / "src"


async def test_what_is_missing_or_the_wrong_kind_is_refused(
    workspace: Workspace,
    workspace_dir: Path,
) -> None:
    (workspace_dir / "src").mkdir()
    (workspace_dir / "a.txt").write_text("a", encoding="utf-8")

    with pytest.raises(PathNotFoundError):
        await workspace.existing("missing")
    with pytest.raises(NotAFileError):
        await workspace.file("src")
    with pytest.raises(NotAFolderError):
        await workspace.folder("a.txt")
