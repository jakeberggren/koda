from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from koda.llm.exceptions import StructuredOutputNotSupportedError
from koda.llm.protocols import LLM

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.llm import LLMEvent, LLMResponse
    from koda.llm.types import LLMRequest
    from koda.messages import AssistantMessage


class LLMProviderBase(LLM):
    def __init__(self, driver: LLM) -> None:
        self.driver: LLM = driver

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        return await self.driver.generate(request)

    def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        return self.driver.generate_stream(request)

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]:
        _ = request, schema
        raise StructuredOutputNotSupportedError
