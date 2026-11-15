from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda.llm.credentials import Credentials
    from koda.llm.models import Connection, Model
    from koda.llm.protocols import LLM
    from koda.llm.types import LLMOptions


@dataclass(frozen=True, slots=True, kw_only=True)
class LLMApiContext:
    """What an API needs to build an LLM: the model, the connection and its credentials,
    the options to ask it with, and for an OpenAI-compatible API, how to make its client."""

    model: Model
    connection: Connection
    credentials: Credentials
    options: LLMOptions
    openai_client: Callable[..., AsyncOpenAI] = AsyncOpenAI

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
