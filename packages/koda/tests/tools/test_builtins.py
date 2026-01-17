"""Integration tests for builtin tools."""

from pathlib import Path

import pytest

from koda.tools import (
    ToolCall,
    ToolContext,
    ToolExecutor,
    ToolRegistry,
    get_builtin_tools,
)


class TestReadFileTool:
    """Integration tests for read_file tool."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, sandbox_dir: Path) -> None:
        """read_file tool can read files within sandbox."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("Hello, World!")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.txt"},
            call_id="call_read",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_read"
        assert result.output.is_error is False
        assert result.output.content["text"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_read_file_outside_sandbox_fails(self, sandbox_dir: Path) -> None:
        """read_file tool fails when reading outside sandbox."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/etc/passwd"},
            call_id="call_escape",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_escape"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "/etc/passwd" in result.output.error_message

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, sandbox_dir: Path) -> None:
        """read_file tool returns error for non-existent file."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "nonexistent.txt"},
            call_id="call_notfound",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_notfound"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "nonexistent.txt" in result.output.error_message


class TestWriteFileTool:
    """Integration tests for write_file tool."""

    @pytest.mark.asyncio
    async def test_write_file_success(self, sandbox_dir: Path) -> None:
        """write_file tool can create files within sandbox."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "new_file.txt", "content": "New content"},
            call_id="call_write",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_write"
        assert result.output.is_error is False

        written_file = sandbox_dir / "new_file.txt"
        assert written_file.exists()
        assert written_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_write_file_creates_parent_dirs(self, sandbox_dir: Path) -> None:
        """write_file tool creates parent directories."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "nested/dir/file.txt", "content": "Nested content"},
            call_id="call_nested",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert (sandbox_dir / "nested" / "dir" / "file.txt").read_text() == "Nested content"

    @pytest.mark.asyncio
    async def test_write_file_outside_sandbox_fails(self, sandbox_dir: Path) -> None:
        """write_file tool fails when writing outside sandbox."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "/tmp/escape.txt", "content": "escaped"},
            call_id="call_escape",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "/tmp/escape.txt" in result.output.error_message


class TestListDirectoryTool:
    """Integration tests for list_directory tool."""

    @pytest.mark.asyncio
    async def test_list_directory_success(self, sandbox_dir: Path) -> None:
        """list_directory tool can list directory contents."""
        (sandbox_dir / "file1.txt").touch()
        (sandbox_dir / "file2.txt").touch()
        (sandbox_dir / "subdir").mkdir()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="list_directory",
            arguments={"path": "."},
            call_id="call_list",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_list"
        assert result.output.is_error is False
        items = result.output.content["items"]
        names = {item["name"] for item in items}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_list_directory_outside_sandbox_fails(self, sandbox_dir: Path) -> None:
        """list_directory tool fails when listing outside sandbox."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="list_directory",
            arguments={"path": "/etc"},
            call_id="call_escape",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "/etc" in result.output.error_message


class TestFileExistsTool:
    """Integration tests for file_exists tool."""

    @pytest.mark.asyncio
    async def test_file_exists_true(self, sandbox_dir: Path) -> None:
        """file_exists returns true for existing file."""
        test_file = sandbox_dir / "exists.txt"
        test_file.touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="file_exists",
            arguments={"path": "exists.txt"},
            call_id="call_exists",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert result.output.content["exists"] is True

    @pytest.mark.asyncio
    async def test_file_exists_false(self, sandbox_dir: Path) -> None:
        """file_exists returns false for non-existent file."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="file_exists",
            arguments={"path": "nonexistent.txt"},
            call_id="call_notexists",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert result.output.content["exists"] is False
