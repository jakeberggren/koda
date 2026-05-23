from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.context.sources import ContextSource, FileContextSource, ProjectFileDiscoverySource
from koda.prompts import SystemPrompt
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

logger = get_logger(__name__)


def _max_mtime_for_paths(paths: Iterable[Path]) -> float | None:
    """Return the latest mtime among existing files, or None if none exist."""
    max_mtime: float | None = None
    for path in paths:
        if path.exists():
            mtime = path.stat().st_mtime
            if max_mtime is None or mtime > max_mtime:
                max_mtime = mtime
    return max_mtime


@dataclass
class _FileCache:
    """Simple cache entry keyed by max mtime of observed files."""

    content: str | None = None
    mtime: float | None = None

    def is_fresh(self, current_mtime: float | None) -> bool:
        return isinstance(self.mtime, (int, float)) and self.mtime == current_mtime


@dataclass
class ContextManager:
    """Collect project-specific context and inject it into the agent system prompt.

    The manager reads from its configured sources and appends their content to
    the base system prompt content. If no sources produce content, the base
    prompt is returned unchanged.

    File contents are cached and only re-read when the observed mtime of
    underlying files changes. This makes the manager safe to call on every
    agent turn without repeated disk I/O.

    Future iterations will add:
    - token budget awareness and reserve tokens
    - compaction strategies when context limits are approached
    """

    sources: Sequence[ContextSource] = field(default_factory=list)
    _cache: _FileCache = field(default_factory=_FileCache, repr=False)

    @classmethod
    def from_workspace(
        cls,
        workspace_root: Path,
        *,
        filenames: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md"),
    ) -> ContextManager:
        """Create a manager that discovers standard project context files."""
        return cls(sources=[ProjectFileDiscoverySource(root=workspace_root, filenames=filenames)])

    @staticmethod
    def _source_mtime(source: ContextSource) -> float | None:
        """Return the latest mtime for file-based sources, or None."""
        if isinstance(source, FileContextSource):
            return source.path.stat().st_mtime if source.path.exists() else None
        if isinstance(source, ProjectFileDiscoverySource):
            return _max_mtime_for_paths(source.root / filename for filename in source.filenames)
        return None

    def _get_max_mtime(self) -> float | None:
        """Return the latest mtime across all sources."""
        max_mtime: float | None = None
        for source in self.sources:
            mtime = self._source_mtime(source)
            if isinstance(mtime, (int, float)) and (max_mtime is None or mtime > max_mtime):
                max_mtime = mtime
        return max_mtime

    def _read_sources(self) -> str | None:
        """Read all sources, using the cache when files haven't changed."""
        current_mtime = self._get_max_mtime()
        if self._cache.is_fresh(current_mtime):
            return self._cache.content

        parts: list[str] = []
        for source in self.sources:
            content = source.read()
            if content is not None:
                parts.append(content)

        result = "\n\n".join(parts) if parts else None
        self._cache = _FileCache(content=result, mtime=current_mtime)
        return result

    def build_system_prompt(self, base: SystemPrompt) -> SystemPrompt:
        """Return the base prompt augmented with project context."""
        content = self._read_sources()
        if content is None:
            logger.debug("no_project_context_found")
            return base
        logger.info("injecting_project_context", source_count=len(self.sources))
        return SystemPrompt(
            content=f"{base.content}\n\n{content}",
            source=base.source,
        )
