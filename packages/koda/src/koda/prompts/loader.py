from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.context.sources import FileContextSource
from koda.prompts.prompt import SystemPrompt
from koda_common.paths import koda_home_dir

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class SystemPromptLoader:
    """Load a system prompt from file or fall back to the default.

    Searches ``search_paths`` in order for ``SYSTEM.md``. The first non-empty
    file found replaces the default prompt entirely. If no file is found, the
    built-in default is returned.

    When ``sandbox_root`` is set, files discovered under that path are confined
    to it (symlinks and path traversal outside the root are rejected). Other
    search paths are read without restriction.
    """

    search_paths: Sequence[Path]
    filename: str = "SYSTEM.md"
    sandbox_root: Path | None = None

    def _root_for_directory(self, directory: Path) -> Path | None:
        if self.sandbox_root is None:
            return None
        try:
            directory_resolved = directory.resolve(strict=True)
            sandbox_resolved = self.sandbox_root.resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        if directory_resolved == sandbox_resolved or directory_resolved.is_relative_to(
            sandbox_resolved
        ):
            return sandbox_resolved
        return None

    @classmethod
    def for_workspace(cls, workspace_root: Path) -> SystemPromptLoader:
        """Create a loader that searches the workspace then ``~/.koda``."""
        return cls(
            search_paths=[workspace_root, koda_home_dir()],
            sandbox_root=workspace_root,
        )

    def load(self) -> SystemPrompt:
        """Return the loaded system prompt."""

        for directory in self.search_paths:
            path = directory / self.filename
            source = FileContextSource(path, trusted_root=self._root_for_directory(directory))
            content = source.read()
            if content is not None:
                return SystemPrompt(content=content, source=path)
        return SystemPrompt()  # default
