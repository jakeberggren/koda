from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TC003
from typing import Protocol

from koda_common.logging import get_logger

logger = get_logger(__name__)


def _resolve_existing(path: Path) -> Path | None:
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _resolve_within_root(path: Path, root: Path) -> Path | None:
    resolved = _resolve_existing(path)
    root_resolved = _resolve_existing(root)
    if resolved is None or root_resolved is None:
        return None
    if resolved.is_relative_to(root_resolved):
        return resolved
    logger.warning(
        "context_file_outside_root",
        path=str(path),
        resolved=str(resolved),
        root=str(root),
    )
    return None


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

    When ``trusted_root`` is provided, the resolved path must stay under the resolved
    root. This prevents symlinks and path-traversal from escaping the trusted
    workspace boundary.
    """

    path: Path
    trusted_root: Path | None = None

    def _resolved_path(self) -> Path | None:
        resolved = (
            _resolve_existing(self.path)
            if self.trusted_root is None
            else _resolve_within_root(self.path, self.trusted_root)
        )
        if resolved is None:
            return None
        if not resolved.is_file():
            return None
        return resolved

    def read(self) -> str | None:
        path = self._resolved_path()
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            logger.warning("context_file_read_failed", path=str(self.path), error=str(error))
            return None
        if not content:
            return None
        return content


@dataclass(frozen=True, slots=True)
class ProjectFileContextSource(ContextSource):
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
            source = FileContextSource(path, trusted_root=self.root)
            content = source.read()
            if content is not None:
                parts.append(content)
        if not parts:
            return None
        return "\n\n".join(parts)
