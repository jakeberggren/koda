from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from pydantic import BaseModel

from koda.llm.types import LLMEvent, LLMRequest, LLMResponse
from koda.messages import AssistantMessage, Message
from koda.tools import ToolCall, ToolDefinition


class LLM(Protocol):
    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse[AssistantMessage]: ...

    def generate_stream(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[LLMEvent]: ...

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]: ...


class LLMAdapter[ProviderMessagesT, ProviderToolsT, ProviderResponseT](Protocol):
    def to_provider_messages(self, messages: Sequence[Message]) -> ProviderMessagesT: ...

    def to_provider_tools(self, tools: Sequence[ToolDefinition] | None) -> ProviderToolsT: ...

    def extract_tool_calls(self, response: ProviderResponseT) -> list[ToolCall]: ...
