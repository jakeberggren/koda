"""Tests for the edit_file tool."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from koda import harness
from koda.harness.workspace import Workspace
from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

from .conftest import content_text

if TYPE_CHECKING:
    from pathlib import Path


class TestEditFileTool:
    """Integration tests for edit_file tool."""

    @pytest.mark.asyncio
    async def test_edit_file_success(self, workspace_dir: Path) -> None:
        """edit_file tool can edit file content."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("line1\nline2")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "line2", "new_text": "line2\nline3"},
            call_id="call_edit",
        )

        result = await executor.execute_call(call)

        assert result.call_id == "call_edit"
        assert result.output.is_error is False
        assert result.output.content["replacements"] == 1
        assert content_text(result, "path") == "test.txt"
        assert "+line3" in content_text(result, "diff")
        assert result.output.display is not None
        assert (workspace_dir / "test.txt").read_text() == "line1\nline2\nline3"

    @pytest.mark.asyncio
    async def test_edit_file_not_found(self, workspace_dir: Path) -> None:
        """edit_file tool returns error for missing file."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "missing.txt", "old_text": "a", "new_text": "b"},
            call_id="call_missing",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "missing.txt" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_not_a_file(self, workspace_dir: Path) -> None:
        """edit_file tool returns error for directory targets."""
        (workspace_dir / "subdir").mkdir()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "subdir", "old_text": "a", "new_text": "b"},
            call_id="call_dir",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "subdir" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_text_not_found(self, workspace_dir: Path) -> None:
        """edit_file tool errors when text is missing."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("line1\nline2")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "line3", "new_text": "x"},
            call_id="call_notfound",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Text not found" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_multiple_matches_fails(self, workspace_dir: Path) -> None:
        """edit_file tool errors on multiple matches without replace_all."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("repeat\nrepeat\nrepeat")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "repeat", "new_text": "once"},
            call_id="call_multiple",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Provide more context" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_replace_all(self, workspace_dir: Path) -> None:
        """edit_file tool can replace all matches."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("repeat\nrepeat\nrepeat")
        expected_replacements = test_file.read_text().count("repeat")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={
                "path": "test.txt",
                "old_text": "repeat",
                "new_text": "done",
                "replace_all": True,
            },
            call_id="call_replace_all",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert result.output.content["replacements"] == expected_replacements
        assert (workspace_dir / "test.txt").read_text() == "\n".join(
            ["done"] * expected_replacements,
        )

    @pytest.mark.asyncio
    async def test_edit_file_no_changes(self, workspace_dir: Path) -> None:
        """edit_file tool returns no changes when replacement is identical."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("same")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "same", "new_text": "same"},
            call_id="call_noop",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert result.output.content["replacements"] == 0
        assert content_text(result, "diff") == ""
        assert result.output.display == "No changes"

    @pytest.mark.asyncio
    async def test_edit_file_read_only_existing_file_fails(self, workspace_dir: Path) -> None:
        """edit_file tool respects read-only permissions on existing files."""
        test_file = workspace_dir / "locked.txt"
        test_file.write_text("line1\nline2")
        test_file.chmod(0o444)

        if os.access(test_file, os.W_OK):
            pytest.skip("platform does not enforce read-only mode for the current user")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        try:
            call = ToolCall(
                tool_name="edit_file",
                arguments={"path": "locked.txt", "old_text": "line2", "new_text": "updated"},
                call_id="call_read_only_edit",
            )

            result = await executor.execute_call(call)
        finally:
            test_file.chmod(0o644)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Permission denied" in result.output.error_message
        assert test_file.read_text() == "line1\nline2"
