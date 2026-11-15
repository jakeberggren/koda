"""Tests for the write_file tool."""

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

import pytest

from koda import harness
from koda.harness.workspace import Workspace
from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

if TYPE_CHECKING:
    from pathlib import Path


class TestWriteFileTool:
    """Integration tests for write_file tool."""

    @pytest.mark.asyncio
    async def test_write_file_success(self, workspace_dir: Path) -> None:
        """write_file tool can create files within the workspace."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "new_file.txt", "content": "New content"},
            call_id="call_write",
        )

        result = await executor.execute_call(call)

        assert result.call_id == "call_write"
        assert result.output.is_error is False

        written_file = workspace_dir / "new_file.txt"
        assert written_file.exists()
        assert written_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, workspace_dir: Path) -> None:
        """write_file tool creates parent directories."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "nested/dir/file.txt", "content": "Nested content"},
            call_id="call_nested",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert (workspace_dir / "nested" / "dir" / "file.txt").read_text() == "Nested content"

    @pytest.mark.asyncio
    async def test_write_file_display(self, workspace_dir: Path) -> None:
        """write_file tool sets appropriate display message."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "output.txt", "content": "line1\nline2"},
            call_id="call_display",
        )

        result = await executor.execute_call(call)

        assert result.output.display is not None
        assert "2 lines" in result.output.display

    @pytest.mark.asyncio
    async def test_write_file_preserves_existing_mode(self, workspace_dir: Path) -> None:
        """write_file tool preserves permissions when updating an existing file."""
        test_file = workspace_dir / "script.sh"
        test_file.write_text("#!/bin/sh\necho old\n")
        test_file.chmod(0o755)

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "script.sh", "content": "#!/bin/sh\necho new\n"},
            call_id="call_preserve_mode",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert stat.S_IMODE(test_file.stat().st_mode) == 0o755

    @pytest.mark.asyncio
    async def test_write_file_read_only_existing_file_fails(self, workspace_dir: Path) -> None:
        """write_file tool respects read-only permissions on existing files."""
        test_file = workspace_dir / "locked.txt"
        test_file.write_text("original")
        test_file.chmod(0o444)

        if os.access(test_file, os.W_OK):
            pytest.skip("platform does not enforce read-only mode for the current user")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        try:
            call = ToolCall(
                tool_name="write_file",
                arguments={"path": "locked.txt", "content": "updated"},
                call_id="call_read_only",
            )

            result = await executor.execute_call(call)
        finally:
            test_file.chmod(0o644)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Permission denied" in result.output.error_message
        assert test_file.read_text() == "original"
