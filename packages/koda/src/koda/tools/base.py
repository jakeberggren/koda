from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from koda.messages import ToolOutput


class Tool[ParamsType: BaseModel](Protocol):
    """A tool the agent can run: ``execute`` takes the model's arguments, validated by
    ``parameters_model``."""

    name: str
    """Unique identifier for the tool."""

    description: str
    """Agent-readable description of what the tool does."""

    parameters_model: type[ParamsType]
    """Pydantic model for validating tool parameters."""

    async def execute(self, params: ParamsType) -> ToolOutput:
        """Execute the tool with validated parameters."""
        ...


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A tool as a request offers it to the model: what it is and what it takes."""

    name: str
    description: str
    parameters_model: type[BaseModel]
