from pathlib import Path

from pydantic import BaseModel, Field

from koda.tools.base import ToolResult

BLACKLISTED_FILES = [".env", ".env.local", ".DS_Store", ".ds_store", ".gitignore"]


class ReadFileParams(BaseModel):
    """Parameters for reading a file."""

    path: str = Field(..., description="Path to the file to read")


class ReadFileTool:
    """Tool for reading file contents."""

    def __init__(self) -> None:
        self.name: str = "read_file"
        self.description: str = "Read the contents of a file from the filesystem"
        self.parameters_model: type[BaseModel] = ReadFileParams

    async def execute(self, params: ReadFileParams) -> ToolResult:
        """Execute the read_file tool. Reading .env files is explicitly forbidden."""
        file_path = Path(params.path)
        file_path = file_path.resolve()

        # Deny reading of .env files regardless of location or casing
        # This is a business rule, so return ToolResult directly
        if file_path.name.lower() in BLACKLISTED_FILES:
            return ToolResult(
                content=None,
                is_error=True,
                error_message=f"Reading {file_path.name} is not allowed.",
            )

        # Let filesystem operations raise their natural exceptions
        # The agent will catch and convert them to ToolResult
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {params.path}")

        if not file_path.is_file():
            raise IsADirectoryError(f"Path is not a file: {params.path}")

        # read_text will raise PermissionError if needed
        content = file_path.read_text(encoding="utf-8")
        return ToolResult(content=content, is_error=False)


class WriteFileParams(BaseModel):
    """Parameters for writing a file."""

    path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")


class WriteFileTool:
    """Tool for writing file contents."""

    def __init__(self) -> None:
        self.name: str = "write_file"
        self.description: str = "Write content to a file on the filesystem"
        self.parameters_model: type[BaseModel] = WriteFileParams

    async def execute(self, params: WriteFileParams) -> ToolResult:
        """Execute the write_file tool."""
        file_path = Path(params.path)
        file_path = file_path.resolve()

        # Business rule: deny writing to blacklisted files
        if file_path.name.lower() in BLACKLISTED_FILES:
            return ToolResult(
                content=None,
                is_error=True,
                error_message=f"Writing to {file_path.name} is not allowed.",
            )

        # Create parent directories if they don't exist
        # mkdir may raise PermissionError - let it propagate
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # write_text will raise PermissionError if needed
        file_path.write_text(params.content, encoding="utf-8")
        return ToolResult(
            content={"success": True, "path": str(file_path)},
            is_error=False,
        )


class ListDirectoryParams(BaseModel):
    """Parameters for listing a directory."""

    path: str = Field(default=".", description="Path to the directory to list")


class ListDirectoryTool:
    """Tool for listing directory contents."""

    def __init__(self) -> None:
        self.name: str = "list_directory"
        self.description: str = "List the contents of a directory"
        self.parameters_model: type[BaseModel] = ListDirectoryParams

    async def execute(self, params: ListDirectoryParams) -> ToolResult:
        """Execute the list_directory tool."""
        dir_path = Path(params.path)
        dir_path = dir_path.resolve()

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {params.path}")

        if not dir_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {params.path}")

        # iterdir will raise PermissionError if needed
        items = []
        for item in dir_path.iterdir():
            items.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item),
                }
            )

        return ToolResult(content=items, is_error=False)


class FileExistsParams(BaseModel):
    """Parameters for checking if a file exists."""

    path: str = Field(..., description="Path to check")


class FileExistsTool:
    """Tool for checking if a file exists."""

    def __init__(self) -> None:
        self.name: str = "file_exists"
        self.description: str = "Check if a file or directory exists"
        self.parameters_model: type[BaseModel] = FileExistsParams

    async def execute(self, params: FileExistsParams) -> ToolResult:
        """Execute the file_exists tool."""
        file_path = Path(params.path)
        file_path = file_path.resolve()

        # exists() shouldn't raise exceptions, but if it does, let it propagate
        exists = file_path.exists()
        return ToolResult(
            content={"exists": exists, "path": str(file_path)},
            is_error=False,
        )
