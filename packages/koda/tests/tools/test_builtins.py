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

    @pytest.mark.asyncio
    async def test_read_file_display(self, sandbox_dir: Path) -> None:
        """read_file tool sets appropriate display message."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("line1\nline2\nline3")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.txt"},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert "3 lines" in result.output.display
        assert "test.txt" in result.output.display


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

    @pytest.mark.asyncio
    async def test_write_file_display(self, sandbox_dir: Path) -> None:
        """write_file tool sets appropriate display message."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="write_file",
            arguments={"path": "output.txt", "content": "line1\nline2"},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert "2 lines" in result.output.display
        assert "output.txt" in result.output.display


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

    @pytest.mark.asyncio
    async def test_list_directory_display(self, sandbox_dir: Path) -> None:
        """list_directory tool sets appropriate display message."""
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
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert "2 files" in result.output.display
        assert "1 director" in result.output.display


class TestGlobTool:
    """Integration tests for glob tool."""

    @pytest.mark.asyncio
    async def test_glob_finds_files(self, sandbox_dir: Path) -> None:
        """glob tool finds files matching pattern."""
        (sandbox_dir / "file1.txt").touch()
        (sandbox_dir / "file2.txt").touch()
        (sandbox_dir / "other.py").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt"},
            call_id="call_glob",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_glob"
        assert result.output.is_error is False
        text = result.output.content["text"]
        assert "file1.txt" in text
        assert "file2.txt" in text
        assert "other.py" not in text

    @pytest.mark.asyncio
    async def test_glob_recursive_pattern(self, sandbox_dir: Path) -> None:
        """glob tool handles recursive ** patterns."""
        subdir = sandbox_dir / "subdir"
        subdir.mkdir()
        nested = subdir / "nested"
        nested.mkdir()
        (sandbox_dir / "root.py").touch()
        (subdir / "middle.py").touch()
        (nested / "deep.py").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "**/*.py"},
            call_id="call_recursive",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        text = result.output.content["text"]
        assert "root.py" in text
        assert "middle.py" in text
        assert "deep.py" in text

    @pytest.mark.asyncio
    async def test_glob_no_matches(self, sandbox_dir: Path) -> None:
        """glob tool returns appropriate message when no files match."""
        (sandbox_dir / "file.txt").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.xyz"},
            call_id="call_nomatch",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert "No files found" in result.output.content["text"]

    @pytest.mark.asyncio
    async def test_glob_respects_limit(self, sandbox_dir: Path) -> None:
        """glob tool truncates results when exceeding limit."""
        total_files = 10
        limit = 5
        for i in range(total_files):
            (sandbox_dir / f"file{i:02d}.txt").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "limit": limit},
            call_id="call_limit",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        text = result.output.content["text"]
        # Count matches - should only have `limit` files listed
        file_count = sum(1 for line in text.split("\n") if line.endswith(".txt"))
        assert file_count == limit
        assert f"showing first {limit}" in text

    @pytest.mark.asyncio
    async def test_glob_path_not_found(self, sandbox_dir: Path) -> None:
        """glob tool returns error for non-existent path."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "path": "nonexistent"},
            call_id="call_notfound",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "nonexistent" in result.output.error_message

    @pytest.mark.asyncio
    async def test_glob_path_not_directory(self, sandbox_dir: Path) -> None:
        """glob tool returns error when path is a file, not directory."""
        (sandbox_dir / "file.txt").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "path": "file.txt"},
            call_id="call_notdir",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None

    @pytest.mark.asyncio
    async def test_glob_outside_sandbox_fails(self, sandbox_dir: Path) -> None:
        """glob tool fails when searching outside sandbox."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*", "path": "/etc"},
            call_id="call_escape",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "/etc" in result.output.error_message

    @pytest.mark.asyncio
    async def test_glob_excludes_directories(self, sandbox_dir: Path) -> None:
        """glob tool only returns files, not directories."""
        (sandbox_dir / "file.txt").touch()
        (sandbox_dir / "subdir").mkdir()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*"},
            call_id="call_filesonly",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        text = result.output.content["text"]
        assert "file.txt" in text
        assert "subdir" not in text

    @pytest.mark.asyncio
    async def test_glob_display_with_matches(self, sandbox_dir: Path) -> None:
        """glob tool sets appropriate display message when files are found."""
        (sandbox_dir / "file1.txt").touch()
        (sandbox_dir / "file2.txt").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt"},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert "Found 2 files" in result.output.display
        assert "*.txt" in result.output.display

    @pytest.mark.asyncio
    async def test_glob_display_no_matches(self, sandbox_dir: Path) -> None:
        """glob tool sets appropriate display message when no files match."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.xyz"},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert "No files found" in result.output.display
        assert "*.xyz" in result.output.display

    @pytest.mark.asyncio
    async def test_glob_display_truncated(self, sandbox_dir: Path) -> None:
        """glob tool display indicates truncation when results exceed limit."""
        total_files = 10
        limit = 5
        for i in range(total_files):
            (sandbox_dir / f"file{i:02d}.txt").touch()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="glob",
            arguments={"pattern": "*.txt", "limit": limit},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert f"Found {total_files} files" in result.output.display
        assert f"showing first {limit}" in result.output.display


class TestGrepTool:
    """Integration tests for grep tool."""

    @pytest.mark.asyncio
    async def test_grep_finds_matches(self, sandbox_dir: Path) -> None:
        """grep tool finds matching lines across files."""
        (sandbox_dir / "file1.txt").write_text("hello\nworld\nhello again")
        (sandbox_dir / "file2.txt").write_text("no match\nhello there")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "hello"},
            call_id="call_grep",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        text = result.output.content["text"]
        assert "file1.txt:1:hello" in text
        assert "file1.txt:3:hello again" in text
        assert "file2.txt:2:hello there" in text

    @pytest.mark.asyncio
    async def test_grep_respects_limit(self, sandbox_dir: Path) -> None:
        """grep tool truncates results when exceeding limit."""
        (sandbox_dir / "file.txt").write_text("match\nmatch\nmatch")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        limit = 2
        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "match", "limit": limit},
            call_id="call_grep_limit",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        text = result.output.content["text"]
        line_count = sum(1 for line in text.split("\n") if line.startswith("file.txt:"))
        assert line_count == limit
        assert "showing first 2" in text

    @pytest.mark.asyncio
    async def test_grep_no_matches(self, sandbox_dir: Path) -> None:
        """grep tool reports when no matches are found."""
        (sandbox_dir / "file.txt").write_text("hello\nworld")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "absent"},
            call_id="call_grep_nomatch",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert "No matches found" in result.output.content["text"]

    @pytest.mark.asyncio
    async def test_grep_path_not_found(self, sandbox_dir: Path) -> None:
        """grep tool errors when path does not exist."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "hello", "path": "missing"},
            call_id="call_grep_notfound",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "missing" in result.output.error_message

    @pytest.mark.asyncio
    async def test_grep_pattern_starting_with_dash(self, sandbox_dir: Path) -> None:
        """grep tool treats patterns starting with '-' as literals."""
        (sandbox_dir / "file.txt").write_text("-match\nother")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "-match"},
            call_id="call_grep_dash",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert "file.txt:1:-match" in result.output.content["text"]

    @pytest.mark.asyncio
    async def test_grep_file_path_formats_relative_path(self, sandbox_dir: Path) -> None:
        """grep tool uses the file name when searching a single file."""
        (sandbox_dir / "file.txt").write_text("hello\nworld")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="grep",
            arguments={"pattern": "hello", "path": "file.txt"},
            call_id="call_grep_file",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert "file.txt:1:hello" in result.output.content["text"]
