"""Tests for the read_file tool."""

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


class TestReadFileTool:
    """Integration tests for read_file tool."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, workspace_dir: Path) -> None:
        """read_file tool can read files within the workspace."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("Hello, World!")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="read_file", arguments={"path": "test.txt"}, call_id="call_read")

        result = await executor.execute_call(call)

        assert result.call_id == "call_read"
        assert result.output.is_error is False
        assert content_text(result, "text") == "Hello, World!"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, workspace_dir: Path) -> None:
        """read_file tool returns error for non-existent file."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "nonexistent.txt"},
            call_id="call_notfound",
        )

        result = await executor.execute_call(call)

        assert result.call_id == "call_notfound"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "nonexistent.txt" in result.output.error_message

    @pytest.mark.asyncio
    async def test_read_file_display(self, workspace_dir: Path) -> None:
        """read_file tool sets appropriate display message."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("line1\nline2\nline3")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.txt", "offset": 0, "limit": 3},
            call_id="call_display",
        )

        result = await executor.execute_call(call)

        assert result.output.display is not None
        assert "3 lines" in result.output.display

    async def test_read_file_offset_limit(self, workspace_dir: Path) -> None:
        """read_file tool can read file contents with offset and limit."""
        test_file = workspace_dir / "test.txt"
        test_file.write_text("line1\nline2\nline3")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.txt", "offset": 1, "limit": 2},
            call_id="call_display",
        )

        result = await executor.execute_call(call)

        assert result.output.content == {"text": "line2\nline3", "encoding": "utf-8"}
        assert "line1" not in result.output.content

        assert result.output.display is not None
        assert result.output.display == "Read 2 lines"

    @pytest.mark.asyncio
    async def test_read_file_binary_returns_tool_error(self, workspace_dir: Path) -> None:
        """read_file tool rejects binary-like files instead of crashing."""
        test_file = workspace_dir / "binary.dat"
        test_file.write_bytes(b"\x00\x01\x02\x03")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "binary.dat"},
            call_id="call_binary",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Failed to decode" in result.output.error_message

    @pytest.mark.asyncio
    async def test_read_file_accepts_utf8_bom(self, workspace_dir: Path) -> None:
        """read_file accepts UTF-8 files with a BOM."""
        test_file = workspace_dir / "bom.txt"
        test_file.write_bytes("hello\nworld\n".encode("utf-8-sig"))

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "bom.txt", "offset": 0, "limit": 2},
            call_id="call_bom",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert result.output.content == {"text": "hello\nworld\n", "encoding": "utf-8-sig"}

    @pytest.mark.asyncio
    async def test_read_file_reads_requested_lines_without_decoding_entire_file(
        self,
        workspace_dir: Path,
    ) -> None:
        """read_file only decodes the requested line window."""
        test_file = workspace_dir / "large.txt"
        test_file.write_bytes(b"line1\nline2\n" + b"a" * 10000 + b"\x80")

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "large.txt", "offset": 0, "limit": 2},
            call_id="call_streaming",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert result.output.content == {"text": "line1\nline2\n", "encoding": "utf-8"}
