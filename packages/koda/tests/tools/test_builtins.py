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
            arguments={"path": "test.txt", "offset": 0, "limit": 3},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.display is not None
        assert "3 lines" in result.output.display

    async def test_read_file_offset_limit(self, sandbox_dir: Path) -> None:
        """read_file tool can read file contents with offset and limit."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("line1\nline2\nline3")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="read_file",
            arguments={"path": "test.txt", "offset": 1, "limit": 2},
            call_id="call_display",
        )

        result = await executor.execute_call(call, context)

        assert result.output.content == {"text": "line2\nline3"}
        assert "line1" not in result.output.content

        assert result.output.display is not None
        assert result.output.display == "Read 2 lines"


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


class TestEditFileTool:
    """Integration tests for edit_file tool."""

    @pytest.mark.asyncio
    async def test_edit_file_success(self, sandbox_dir: Path) -> None:
        """edit_file tool can edit file content."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("line1\nline2")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={
                "path": "test.txt",
                "old_text": "line2",
                "new_text": "line2\nline3",
            },
            call_id="call_edit",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_edit"
        assert result.output.is_error is False
        assert result.output.content["replacements"] == 1
        assert result.output.content["path"] == "test.txt"
        assert "+line3" in result.output.content["diff"]
        assert result.output.display is not None
        assert (sandbox_dir / "test.txt").read_text() == "line1\nline2\nline3"

    @pytest.mark.asyncio
    async def test_edit_file_outside_sandbox_fails(self, sandbox_dir: Path) -> None:
        """edit_file tool fails when editing outside sandbox."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "/etc/passwd", "old_text": "root", "new_text": "r"},
            call_id="call_escape",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "/etc/passwd" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_not_found(self, sandbox_dir: Path) -> None:
        """edit_file tool returns error for missing file."""
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "missing.txt", "old_text": "a", "new_text": "b"},
            call_id="call_missing",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "missing.txt" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_not_a_file(self, sandbox_dir: Path) -> None:
        """edit_file tool returns error for directory targets."""
        (sandbox_dir / "subdir").mkdir()

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "subdir", "old_text": "a", "new_text": "b"},
            call_id="call_dir",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "subdir" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_text_not_found(self, sandbox_dir: Path) -> None:
        """edit_file tool errors when text is missing."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("line1\nline2")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "line3", "new_text": "x"},
            call_id="call_notfound",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Text not found" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_multiple_matches_fails(self, sandbox_dir: Path) -> None:
        """edit_file tool errors on multiple matches without replace_all."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("repeat\nrepeat\nrepeat")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "repeat", "new_text": "once"},
            call_id="call_multiple",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Provide more context" in result.output.error_message

    @pytest.mark.asyncio
    async def test_edit_file_replace_all(self, sandbox_dir: Path) -> None:
        """edit_file tool can replace all matches."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("repeat\nrepeat\nrepeat")
        expected_replacements = test_file.read_text().count("repeat")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

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

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert result.output.content["replacements"] == expected_replacements
        assert (sandbox_dir / "test.txt").read_text() == "\n".join(["done"] * expected_replacements)

    @pytest.mark.asyncio
    async def test_edit_file_no_changes(self, sandbox_dir: Path) -> None:
        """edit_file tool returns no changes when replacement is identical."""
        test_file = sandbox_dir / "test.txt"
        test_file.write_text("same")

        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="edit_file",
            arguments={"path": "test.txt", "old_text": "same", "new_text": "same"},
            call_id="call_noop",
        )

        result = await executor.execute_call(call, context)

        assert result.output.is_error is False
        assert result.output.content["replacements"] == 0
        assert result.output.content["diff"] == ""
        assert result.output.display == "No changes"


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
