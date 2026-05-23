from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TC003
from typing import Protocol

from koda_common.logging import get_logger

logger = get_logger(__name__)


class ContextSource(Protocol):
    """Source of project-specific context content."""

    def read(self) -> str | None:
        """Return context content, or None if this source has no content."""
        ...


@dataclass(frozen=True, slots=True)
class FileContextSource(ContextSource):
    """Read context from a specific file path.

    If the file does not exist, returns None. If the file exists but is empty
    or contains only whitespace, returns None.
    """

    path: Path

    def read(self) -> str | None:
        if not self.path.is_file():
            return None
        try:
            content = self.path.read_text(encoding="utf-8").strip()
        except OSError as error:
            logger.warning("context_file_read_failed", path=str(self.path), error=str(error))
            return None
        if not content:
            return None
        return content


@dataclass(frozen=True, slots=True)
class ProjectFileDiscoverySource(ContextSource):
    """Discover and read known project context files from a directory.

    Reads files in the order specified by ``filenames`` and concatenates
    their contents with a separator. The first file found wins per name —
    if multiple files with the same name exist (e.g. across parent dirs),
    only the first is read.
    """

    root: Path
    filenames: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md")

    def read(self) -> str | None:
        parts: list[str] = []
        for filename in self.filenames:
            path = self.root / filename
            source = FileContextSource(path)
            content = source.read()
            if content is not None:
                parts.append(content)
        if not parts:
            return None
        return "\n\n".join(parts)
