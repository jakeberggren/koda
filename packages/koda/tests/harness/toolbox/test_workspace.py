"""Tests for the workspace: how the tools resolve paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from koda.harness.toolbox.workspace import Workspace


def test_a_relative_path_is_relative_to_the_root(workspace: Workspace, workspace_dir: Path) -> None:
    assert workspace.resolve("src/a.py") == workspace_dir / "src" / "a.py"


def test_a_path_outside_the_root_is_allowed(workspace: Workspace, workspace_dir: Path) -> None:
    assert workspace.resolve("../elsewhere.txt") == workspace_dir.parent / "elsewhere.txt"


def test_an_absolute_path_stays_as_it_is(workspace: Workspace, tmp_path: Path) -> None:
    assert workspace.resolve(str(tmp_path / "x.txt")) == (tmp_path / "x.txt").resolve()
