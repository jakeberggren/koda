from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.prompts import SystemPrompt

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm import LLM
    from koda.tools import ToolConfig


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalRuntimeConfig:
    """Configuration for the local application runtime."""

    cwd: Path
    sandbox_dir: Path
    system_prompt: SystemPrompt = field(default_factory=SystemPrompt)
    max_tool_iterations: int = 30
    tools: ToolConfig | None = None
    llm: LLM | None = None
