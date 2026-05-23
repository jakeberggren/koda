from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.context.sources import ContextSource, ProjectFileContextSource
from koda.prompts.prompt import SystemPrompt
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

logger = get_logger(__name__)


@dataclass
class ContextManager:
    """Collect project-specific context and inject it into the agent system prompt.

    The manager reads from its configured sources and appends their content to
    the base system prompt content. If no sources produce content, the base
    prompt is returned unchanged.

    Future iterations will add:
    - token budget awareness and reserve tokens
    - compaction strategies when context limits are approached
    """

    sources: Sequence[ContextSource] = field(default_factory=list)

    @classmethod
    def from_workspace(
        cls,
        workspace_root: Path,
        *,
        filenames: tuple[str, ...] = ("AGENTS.md", "CLAUDE.md"),
    ) -> ContextManager:
        """Create a manager that discovers standard project context files."""
        return cls(sources=[ProjectFileContextSource(root=workspace_root, filenames=filenames)])

    def _read_sources(self) -> str | None:
        """Read all configured context sources."""
        parts: list[str] = []
        for source in self.sources:
            content = source.read()
            if content is not None:
                parts.append(content)

        return "\n\n".join(parts) if parts else None

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
