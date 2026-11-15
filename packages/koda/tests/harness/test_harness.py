"""Tests for the harness: the instructions and tools for working in a folder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda import harness
from koda.harness.prompt import DEFAULT_PROMPT
from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A home directory with an empty ``.koda``, so the real one is never read."""
    home = tmp_path_factory.mktemp("home")
    (home / ".koda").mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.mark.usefixtures("home")
def test_without_files_it_is_the_default_prompt(tmp_path: Path) -> None:
    assert harness.instructions(tmp_path) == DEFAULT_PROMPT


@pytest.mark.usefixtures("home")
def test_agents_md_and_claude_md_follow_the_system_prompt(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Claude notes.", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Agent notes.", encoding="utf-8")

    assert harness.instructions(tmp_path) == f"{DEFAULT_PROMPT}\n\nAgent notes.\n\nClaude notes."


def test_the_folders_system_md_replaces_the_default(tmp_path: Path, home: Path) -> None:
    (tmp_path / "SYSTEM.md").write_text("Workspace prompt.", encoding="utf-8")
    (home / ".koda" / "SYSTEM.md").write_text("Global prompt.", encoding="utf-8")

    assert harness.instructions(tmp_path) == "Workspace prompt."


def test_the_global_system_md_replaces_the_default(tmp_path: Path, home: Path) -> None:
    (home / ".koda" / "SYSTEM.md").write_text("Global prompt.", encoding="utf-8")

    assert harness.instructions(tmp_path) == "Global prompt."


@pytest.mark.usefixtures("home")
def test_empty_files_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "SYSTEM.md").write_text("  \n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")

    assert harness.instructions(tmp_path) == DEFAULT_PROMPT


def test_the_tools_come_in_a_fixed_order(tmp_path: Path) -> None:
    assert [tool.name for tool in harness.tools(tmp_path)] == [
        "bash",
        "edit_file",
        "glob",
        "grep",
        "read_file",
        "write_file",
    ]


async def test_the_tools_work_in_the_folder(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("in the folder", encoding="utf-8")
    executor = ToolExecutor(ToolRegistry(harness.tools(tmp_path)))
    call = ToolCall(tool_name="read_file", arguments={"path": "notes.txt"}, call_id="read")

    result = await executor.execute_call(call)

    assert result.output.content["text"] == "in the folder"
