from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from pydantic import BaseModel

from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
from koda.messages import AssistantMessage, Message
from koda.tools import ToolDefinition


class LLM(Protocol):
    """Runtime interface implemented by concrete model APIs.

    Implementations own provider transport, error translation, and request execution while
    exposing provider-neutral Koda request and response types to the rest of the system.
    """

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse[AssistantMessage]:
        """Generate a complete assistant response for one request."""
        ...

    def generate_stream(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[LLMEvent]:
        """Generate provider-neutral stream events for one request."""
        ...

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]:
        """Generate a response parsed into the requested Pydantic schema."""
        ...


class LLMAdapter[ProviderMessagesT, ProviderToolsT, ProviderResponseT](Protocol):
    """Convert between Koda's LLM types and provider-specific SDK types.

    Adapters should stay transport-free: they shape messages/tools before a request and adapt
    provider responses back into Koda's common response model.
    """

    def to_provider_messages(
        self,
        messages: Sequence[Message],
    ) -> ProviderMessagesT:
        """Convert Koda conversation messages into the provider request format."""
        ...

    def to_provider_tools(
        self,
        tools: Sequence[ToolDefinition] | None,
    ) -> ProviderToolsT:
        """Convert Koda tool definitions into the provider request format."""
        ...

    def to_llm_response(
        self,
        response: ProviderResponseT,
    ) -> LLMResponse[AssistantMessage]:
        """Convert a provider response into Koda's common assistant response."""
        ...
