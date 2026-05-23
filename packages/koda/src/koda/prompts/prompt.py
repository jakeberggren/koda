from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
