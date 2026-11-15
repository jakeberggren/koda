"""Tests for the glob tool."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda import harness
from koda.harness.workspace import Workspace
from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

from .conftest import content_text

if TYPE_CHECKING:
    from pathlib import Path


class TestGlobTool:
    """Integration tests for glob tool."""

    @pytest.mark.asyncio
    async def test_glob_finds_files(self, workspace_dir: Path) -> None:
        """glob tool finds files matching pattern."""
        (workspace_dir / "file1.txt").touch()
        (workspace_dir / "file2.txt").touch()
        (workspace_dir / "other.py").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="glob", arguments={"pattern": "*.txt"}, call_id="call_glob")

        result = await executor.execute_call(call)

        assert result.call_id == "call_glob"
        assert result.output.is_error is False
        text = content_text(result, "text")
        assert "file1.txt" in text
        assert "file2.txt" in text
        assert "other.py" not in text

    @pytest.mark.asyncio
    async def test_glob_leaves_out_ignored_files_and_version_control(
        self,
        workspace_dir: Path,
    ) -> None:
        """glob tool leaves out what the workspace's .gitignore excludes, and .git."""
        (workspace_dir / ".gitignore").write_text("node_modules/\n")
        for path in ["src/app.js", "node_modules/lib/index.js", ".git/hooks/pre-commit.js"]:
            (workspace_dir / path).parent.mkdir(parents=True, exist_ok=True)
            (workspace_dir / path).touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))
        call = ToolCall(tool_name="glob", arguments={"pattern": "**/*.js"}, call_id="call_glob")

        result = await executor.execute_call(call)

        assert content_text(result, "text").splitlines()[1:] == ["src/app.js"]

    @pytest.mark.asyncio
    async def test_glob_recursive_pattern(self, workspace_dir: Path) -> None:
        """glob tool handles recursive ** patterns."""
        subdir = workspace_dir / "subdir"
        subdir.mkdir()
        nested = subdir / "nested"
        nested.mkdir()
        (workspace_dir / "root.py").touch()
        (subdir / "middle.py").touch()
        (nested / "deep.py").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "**/*.py"},
            call_id="call_recursive",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        text = content_text(result, "text")
        assert "root.py" in text
        assert "middle.py" in text
        assert "deep.py" in text

    @pytest.mark.asyncio
    async def test_glob_no_matches(self, workspace_dir: Path) -> None:
        """glob tool returns appropriate message when no files match."""
        (workspace_dir / "file.txt").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="glob", arguments={"pattern": "*.xyz"}, call_id="call_nomatch")

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert "No files found" in content_text(result, "text")

    @pytest.mark.asyncio
    async def test_glob_respects_limit(self, workspace_dir: Path) -> None:
        """glob tool truncates results when exceeding limit."""
        total_files = 10
        limit = 5
        for i in range(total_files):
            (workspace_dir / f"file{i:02d}.txt").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "limit": limit},
            call_id="call_limit",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        text = content_text(result, "text")
        # Count matches - should only have `limit` files listed
        file_count = sum(1 for line in text.split("\n") if line.endswith(".txt"))
        assert file_count == limit
        assert f"showing first {limit}" in text

    @pytest.mark.asyncio
    async def test_glob_path_not_found(self, workspace_dir: Path) -> None:
        """glob tool returns error for non-existent path."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "path": "nonexistent"},
            call_id="call_notfound",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "nonexistent" in result.output.error_message

    @pytest.mark.asyncio
    async def test_glob_path_not_directory(self, workspace_dir: Path) -> None:
        """glob tool returns error when path is a file, not directory."""
        (workspace_dir / "file.txt").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "path": "file.txt"},
            call_id="call_notdir",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None

    @pytest.mark.asyncio
    async def test_glob_excludes_directories(self, workspace_dir: Path) -> None:
        """glob tool only returns files, not directories."""
        (workspace_dir / "file.txt").touch()
        (workspace_dir / "subdir").mkdir()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="glob", arguments={"pattern": "*"}, call_id="call_filesonly")

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        text = content_text(result, "text")
        assert "file.txt" in text
        assert "subdir" not in text

    @pytest.mark.asyncio
    async def test_glob_display_with_matches(self, workspace_dir: Path) -> None:
        """glob tool sets appropriate display message when files are found."""
        (workspace_dir / "file1.txt").touch()
        (workspace_dir / "file2.txt").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="glob", arguments={"pattern": "*.txt"}, call_id="call_display")

        result = await executor.execute_call(call)

        assert result.output.display is not None
        assert "Found 2 files" in result.output.display
        assert "*.txt" in result.output.display

    @pytest.mark.asyncio
    async def test_glob_display_no_matches(self, workspace_dir: Path) -> None:
        """glob tool sets appropriate display message when no files match."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="glob", arguments={"pattern": "*.xyz"}, call_id="call_display")

        result = await executor.execute_call(call)

        assert result.output.display is not None
        assert "No files found" in result.output.display
        assert "*.xyz" in result.output.display

    @pytest.mark.asyncio
    async def test_glob_display_truncated(self, workspace_dir: Path) -> None:
        """glob tool display indicates truncation when results exceed limit."""
        total_files = 10
        limit = 5
        for i in range(total_files):
            (workspace_dir / f"file{i:02d}.txt").touch()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "limit": limit},
            call_id="call_display",
        )

        result = await executor.execute_call(call)

        assert result.output.display is not None
        assert f"Found {total_files} files" in result.output.display
        assert f"showing first {limit}" in result.output.display
