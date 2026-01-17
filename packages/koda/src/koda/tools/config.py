from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koda.tools.context import ToolContext
    from koda.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Bundle of tool registry and execution context."""

    registry: ToolRegistry
    context: ToolContext
