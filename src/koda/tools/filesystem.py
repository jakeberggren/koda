from pathlib import Path

from pydantic import BaseModel, Field

from koda.tools.base import ToolOutput
from koda.utils import exceptions

BLACKLISTED_FILES = [".env", ".env.local", ".DS_Store", ".ds_store", ".gitignore"]


def _validate_path_in_sandbox(file_path: Path, sandbox_dir: Path) -> None:
    """Validate that a resolved path is within the sandbox directory.

    Raises ToolValidationError if the path is outside the sandbox.
    """
    resolved_path = file_path.resolve()
    resolved_sandbox = sandbox_dir.resolve()

    if not resolved_path.is_relative_to(resolved_sandbox):
        raise exceptions.ToolValidationError(
            f"Path '{resolved_path}' is outside the sandbox directory '{resolved_sandbox}'"
        )


class ReadFileParams(BaseModel):
    """Parameters for reading a file."""

    path: str = Field(..., description="Path to the file to read")


class ReadFileTool:
    """Tool for reading file contents."""

    def __init__(self, sandbox_dir: Path | str | None = None) -> None:
        self.name: str = "read_file"
        self.description: str = "Read the contents of a file from the filesystem"
        self.parameters_model: type[BaseModel] = ReadFileParams
        self.sandbox_dir: Path = (
            Path(sandbox_dir).resolve() if sandbox_dir else Path.cwd().resolve()
        )

    async def execute(self, params: ReadFileParams) -> ToolOutput:
        """Execute the read_file tool. Reading .env files is explicitly forbidden."""
        file_path = Path(params.path)
        file_path = file_path.resolve()

        # Validate path is within sandbox
        _validate_path_in_sandbox(file_path, self.sandbox_dir)

        # Deny reading of .env files regardless of location or casing
        if file_path.name.lower() in BLACKLISTED_FILES:
            return ToolOutput(
                is_error=True,
                error_message=f"Reading {file_path.name} is not allowed.",
            )

        # Let filesystem operations raise their natural exceptions
        # The agent will catch and convert them to ToolOutput
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {params.path}")

        if not file_path.is_file():
            raise IsADirectoryError(f"Path is not a file: {params.path}")

        # read_text will raise PermissionError if needed
        text_content = file_path.read_text(encoding="utf-8")
        return ToolOutput(content={"text": text_content})


class WriteFileParams(BaseModel):
    """Parameters for writing a file."""

    path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")


class WriteFileTool:
    """Tool for writing file contents."""

    def __init__(self, sandbox_dir: Path | str | None = None) -> None:
        self.name: str = "write_file"
        self.description: str = "Write content to a file on the filesystem"
        self.parameters_model: type[BaseModel] = WriteFileParams
        self.sandbox_dir: Path = (
            Path(sandbox_dir).resolve() if sandbox_dir else Path.cwd().resolve()
        )

    async def execute(self, params: WriteFileParams) -> ToolOutput:
        """Execute the write_file tool."""
        file_path = Path(params.path)
        file_path = file_path.resolve()

        # Validate path is within sandbox
        _validate_path_in_sandbox(file_path, self.sandbox_dir)

        # Business rule: deny writing to blacklisted files
        if file_path.name.lower() in BLACKLISTED_FILES:
            return ToolOutput(
                is_error=True,
                error_message=f"Writing to {file_path.name} is not allowed.",
            )

        # Create parent directories if they don't exist
        # Validate parent directory is also within sandbox
        _validate_path_in_sandbox(file_path.parent, self.sandbox_dir)
        # mkdir may raise PermissionError - let it propagate
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # write_text will raise PermissionError if needed
        file_path.write_text(params.content, encoding="utf-8")
        return ToolOutput(content={"success": True, "path": str(file_path)})


class ListDirectoryParams(BaseModel):
    """Parameters for listing a directory."""

    path: str = Field(default=".", description="Path to the directory to list")


class ListDirectoryTool:
    """Tool for listing directory contents."""

    def __init__(self, sandbox_dir: Path | str | None = None) -> None:
        self.name: str = "list_directory"
        self.description: str = "List the contents of a directory"
        self.parameters_model: type[BaseModel] = ListDirectoryParams
        self.sandbox_dir: Path = (
            Path(sandbox_dir).resolve() if sandbox_dir else Path.cwd().resolve()
        )

    async def execute(self, params: ListDirectoryParams) -> ToolOutput:
        """Execute the list_directory tool."""
        dir_path = Path(params.path)
        dir_path = dir_path.resolve()

        # Validate path is within sandbox
        _validate_path_in_sandbox(dir_path, self.sandbox_dir)

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {params.path}")

        if not dir_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {params.path}")

        # iterdir will raise PermissionError if needed
        items = []
        for item in dir_path.iterdir():
            # Ensure listed items are also within sandbox (defense in depth)
            item_resolved = item.resolve()
            try:
                _validate_path_in_sandbox(item_resolved, self.sandbox_dir)
            except exceptions.ToolValidationError:
                # Skip items outside sandbox (shouldn't happen, but be safe)
                continue
            items.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item),
                }
            )

        return ToolOutput(content={"items": items})


class FileExistsParams(BaseModel):
    """Parameters for checking if a file exists."""

    path: str = Field(..., description="Path to check")


class FileExistsTool:
    """Tool for checking if a file exists."""

    def __init__(self, sandbox_dir: Path | str | None = None) -> None:
        self.name: str = "file_exists"
        self.description: str = "Check if a file or directory exists"
        self.parameters_model: type[BaseModel] = FileExistsParams
        self.sandbox_dir: Path = (
            Path(sandbox_dir).resolve() if sandbox_dir else Path.cwd().resolve()
        )

    async def execute(self, params: FileExistsParams) -> ToolOutput:
        """Execute the file_exists tool."""
        file_path = Path(params.path)
        file_path = file_path.resolve()

        # Validate path is within sandbox
        _validate_path_in_sandbox(file_path, self.sandbox_dir)

        # exists() shouldn't raise exceptions, but if it does, let it propagate
        exists = file_path.exists()
        return ToolOutput(content={"exists": exists, "path": str(file_path)})
