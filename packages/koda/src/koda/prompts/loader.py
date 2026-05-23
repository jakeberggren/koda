from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.context.sources import FileContextSource
from koda_common.paths import koda_home_dir

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

DEFAULT_SYSTEM_PROMPT: str = (
    "You are Koda, an expert coding assistant built to help the user "
    "navigate, understand, and modify codebases.\n\n"
    "You are running in an execution environment with session state and tool support.\n\n"
    "Be clear, practical, and concise. "
    "Prefer concrete next steps and implementation details when helpful.\n\n"
    "When working with code, preserve the user's intent, avoid unnecessary changes, "
    "and call out important assumptions or risks."
)


@dataclass(frozen=True, slots=True)
class SystemPrompt:
    """A system prompt with provenance for UI display."""

    content: str = DEFAULT_SYSTEM_PROMPT
    source: Path | None = None
    """Path the prompt was loaded from, or ``None`` for the built-in default."""

    def render(self) -> str | None:
        """Render into the final string form."""
        normalized = self.content.strip()
        return normalized or None


@dataclass(frozen=True, slots=True)
class SystemPromptLoader:
    """Load a system prompt from file or fall back to the default.

    Searches ``search_paths`` in order for ``SYSTEM.md``. The first non-empty
    file found replaces the default prompt entirely. If no file is found, the
    built-in default is returned.
    """

    search_paths: Sequence[Path]
    filename: str = "SYSTEM.md"

    @classmethod
    def for_workspace(cls, workspace_root: Path) -> SystemPromptLoader:
        """Create a loader that searches the workspace then ``~/.koda``."""
        return cls(search_paths=[workspace_root, koda_home_dir()])

    def load(self) -> SystemPrompt:
        """Return the loaded system prompt."""

        for directory in self.search_paths:
            path = directory / self.filename
            source = FileContextSource(path)
            content = source.read()
            if content is not None:
                return SystemPrompt(content=content, source=path)
        return SystemPrompt()  # default
