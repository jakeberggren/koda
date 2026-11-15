"""The harness: what makes an agent capable in a folder. Its instructions (SYSTEM.md,
AGENTS.md and CLAUDE.md) and its tools (files, search and the shell), built on the
kernel, which never imports it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda.harness.prompt import instructions
from koda.harness.toolbox.bash import BashTool
from koda.harness.toolbox.edit import EditFileTool
from koda.harness.toolbox.glob import GlobTool
from koda.harness.toolbox.grep import GrepTool
from koda.harness.toolbox.read import ReadFileTool
from koda.harness.toolbox.workspace import Workspace
from koda.harness.toolbox.write import WriteFileTool

if TYPE_CHECKING:
    from pathlib import Path

    from koda.tools import Tool


def tools(path: Path) -> list[Tool]:
    """The built-in tools, working in ``path`` and sharing its locks."""
    workspace = Workspace(path.resolve())
    return [
        BashTool(workspace),
        EditFileTool(workspace),
        GlobTool(workspace),
        GrepTool(workspace),
        ReadFileTool(workspace),
        WriteFileTool(workspace),
    ]


__all__ = ["instructions", "tools"]
