"""The harness: what turns the kernel's agent into a coding agent working in a folder. The
workspace (the folder), the instructions for it and the tools that work in it; the kernel
never imports it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda.harness.prompt import instructions
from koda.harness.toolbox.files import EditFileTool, ReadFileTool, WriteFileTool
from koda.harness.toolbox.search import GlobTool, GrepTool
from koda.harness.toolbox.shell import BashTool
from koda.harness.workspace import Workspace

if TYPE_CHECKING:
    from koda.tools import Tool


def tools(workspace: Workspace) -> list[Tool]:
    """The built-in tools, working in ``workspace``."""
    return [
        BashTool(workspace),
        EditFileTool(workspace),
        GlobTool(workspace),
        GrepTool(workspace),
        ReadFileTool(workspace),
        WriteFileTool(workspace),
    ]


__all__ = ["Workspace", "instructions", "tools"]
