"""Tests for the workspace's files: what its ignore files and SKIPPED leave out."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from koda.harness.workspace import Workspace

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def project(workspace_dir: Path) -> Path:
    for path in [
        "README.md",
        ".env",
        "src/app.py",
        "build/output.js",
        "notes.log",
        ".git/config",
        ".DS_Store",
    ]:
        (workspace_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (workspace_dir / path).write_text("")
    (workspace_dir / ".gitignore").write_text("# build artefacts\nbuild/\n*.log\n")
    return workspace_dir


def test_files_leave_out_what_is_ignored_version_control_and_clutter(project: Path) -> None:
    assert Workspace(project).files() == [".env", ".gitignore", "README.md", "src/app.py"]


def test_files_in_a_folder_are_relative_to_it(project: Path) -> None:
    assert Workspace(project).files(project / "src") == ["app.py"]


def test_files_are_read_from_disk_each_time(project: Path) -> None:
    workspace = Workspace(project)
    workspace.files()
    (project / "new.py").write_text("")

    assert "new.py" in workspace.files()


def test_files_follow_nested_ignore_files_and_include_hidden_ones(project: Path) -> None:
    (project / ".github").mkdir()
    (project / ".github" / "ci.yml").write_text("")
    (project / "src" / ".gitignore").write_text("generated.py\n")
    (project / "src" / "generated.py").write_text("")

    files = Workspace(project).files()

    assert ".github/ci.yml" in files
    assert "src/generated.py" not in files


def test_ignore_files_apply_outside_a_git_repository(project: Path) -> None:
    shutil.rmtree(project / ".git")

    assert "notes.log" not in Workspace(project).files()


def test_a_deeper_ignore_file_can_take_back_what_one_above_excludes(project: Path) -> None:
    (project / "logs").mkdir()
    (project / "logs" / "keep.log").write_text("")
    (project / "logs" / ".gitignore").write_text("!keep.log\n")

    assert "logs/keep.log" in Workspace(project).files()


def test_a_folder_follows_the_ignore_files_above_it(project: Path) -> None:
    (project / "src" / "debug.log").write_text("")

    assert Workspace(project).files(project / "src") == ["app.py"]


def test_dot_ignore_has_the_last_word(project: Path) -> None:
    (project / ".ignore").write_text("!notes.log\n")

    assert "notes.log" in Workspace(project).files()
