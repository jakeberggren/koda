"""Tests for the grep tool."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from koda import harness
from koda.harness.workspace import Workspace
from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

from .conftest import content_text

if TYPE_CHECKING:
    from pathlib import Path


class TestGrepTool:
    """Integration tests for grep tool."""

    rg_required = pytest.mark.skipif(
        shutil.which("rg") is None,
        reason="ripgrep (rg) is not installed",
    )

    @rg_required
    @pytest.mark.requires_rg
    @pytest.mark.asyncio
    async def test_grep_finds_matches(self, workspace_dir: Path) -> None:
        """grep tool finds matching lines across files."""
        (workspace_dir / "file1.txt").write_text("hello\nworld\nhello again")
        (workspace_dir / "file2.txt").write_text("no match\nhello there")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="grep", arguments={"pattern": "hello"}, call_id="call_grep")

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        text = content_text(result, "text")
        assert "file1.txt:1:hello" in text
        assert "file1.txt:3:hello again" in text
        assert "file2.txt:2:hello there" in text

    @rg_required
    @pytest.mark.requires_rg
    @pytest.mark.asyncio
    async def test_grep_searches_the_files_the_workspace_has(self, workspace_dir: Path) -> None:
        """grep searches what Workspace.files lists: hidden files, not ignored ones."""
        (workspace_dir / ".gitignore").write_text("build/\n")
        for path in [".github/ci.yml", "src/app.py", "src/gen.py", "build/out.js", ".git/config"]:
            (workspace_dir / path).parent.mkdir(parents=True, exist_ok=True)
            (workspace_dir / path).write_text("needle\n")
        (workspace_dir / "src" / ".gitignore").write_text("gen.py\n")
        workspace = Workspace(workspace_dir)
        executor = ToolExecutor(ToolRegistry(harness.tools(workspace)))
        call = ToolCall(tool_name="grep", arguments={"pattern": "needle"}, call_id="call_grep")

        text = content_text(await executor.execute_call(call), "text")

        searched = {path for path in workspace.files() if path in text}
        assert searched == {".github/ci.yml", "src/app.py"}
        assert not any(path in text for path in ["src/gen.py", "build/out.js", ".git/config"])

    @pytest.mark.asyncio
    async def test_grep_respects_limit(self, workspace_dir: Path) -> None:
        """grep tool truncates results when exceeding limit."""
        (workspace_dir / "file.txt").write_text("match\nmatch\nmatch")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        limit = 2
        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "match", "limit": limit},
            call_id="call_grep_limit",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        text = content_text(result, "text")
        line_count = sum(1 for line in text.split("\n") if line.startswith("file.txt:"))
        assert line_count == limit
        assert "showing first 2" in text

    @rg_required
    @pytest.mark.requires_rg
    @pytest.mark.asyncio
    async def test_grep_no_matches(self, workspace_dir: Path) -> None:
        """grep tool reports when no matches are found."""
        (workspace_dir / "file.txt").write_text("hello\nworld")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "absent"},
            call_id="call_grep_nomatch",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert "No matches found" in content_text(result, "text")

    @pytest.mark.asyncio
    async def test_grep_path_not_found(self, workspace_dir: Path) -> None:
        """grep tool errors when path does not exist."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "hello", "path": "missing"},
            call_id="call_grep_notfound",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "missing" in result.output.error_message

    @rg_required
    @pytest.mark.requires_rg
    @pytest.mark.asyncio
    async def test_grep_pattern_starting_with_dash(self, workspace_dir: Path) -> None:
        """grep tool treats patterns starting with '-' as literals."""
        (workspace_dir / "file.txt").write_text("-match\nother")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="grep", arguments={"pattern": "-match"}, call_id="call_grep_dash")

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert "file.txt:1:-match" in content_text(result, "text")

    @rg_required
    @pytest.mark.requires_rg
    @pytest.mark.asyncio
    async def test_grep_file_path_formats_relative_path(self, workspace_dir: Path) -> None:
        """grep tool uses the file name when searching a single file."""
        (workspace_dir / "file.txt").write_text("hello\nworld")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "hello", "path": "file.txt"},
            call_id="call_grep_file",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert "file.txt:1:hello" in content_text(result, "text")
