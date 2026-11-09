from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from koda.llm.auth.registry import ProviderAuthRegistry
    from koda.llm.models import Connection, Model
    from koda.llm.protocols import LLM, Credentials


@dataclass(frozen=True, slots=True, kw_only=True)
class LLMApiContext:
    """What an API needs to build an LLM: the model, the connection and its credentials."""

    model: Model
    connection: Connection
    credentials: Credentials
    auth_registry: ProviderAuthRegistry
    tracing: bool = False

    @property
    def capabilities(self) -> dict[str, object]:
        """The connection's capabilities, overridden by the model's."""
        return self.connection.capabilities | self.model.capabilities


class LLMApi(Protocol):
    """An LLM API implementation, built from a connection to a model."""

    @classmethod
    async def from_context(cls, context: LLMApiContext) -> LLM:
        """Build the LLM for ``context``."""
        ...
