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


class LLMAdapter[MessagesT, ToolsT, ResponseT](Protocol):
    def adapt_messages(self, messages: Sequence[Message]) -> MessagesT: ...

    def adapt_tools(self, tools: list[ToolDefinition] | None) -> ToolsT: ...

    def parse_tool_calls(self, response: ResponseT) -> list[ToolCall]: ...
