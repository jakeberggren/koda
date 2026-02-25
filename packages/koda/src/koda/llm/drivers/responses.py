from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI, Omit, omit
from openai.types.responses import FunctionToolParam, Response, ResponseInputParam

from koda.llm import LLMResponse, LLMTokenUsage
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.utils import raise_llm_error_from_openai
from koda.messages import AssistantMessage
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda.llm.types import LLMRequest


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ResponsesDriverConfig:
    api_key: str
    model: str
    base_url: str | None = None


class ResponsesDriver(LLM):
    def __init__(
        self,
        config: ResponsesDriverConfig,
        *,
        adapter: ResponsesDriverAdapter | None = None,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
    ) -> None:
        self.config: ResponsesDriverConfig = config
        self.adapter: ResponsesDriverAdapter = adapter or ResponsesDriverAdapter()
        self.client: AsyncOpenAI = client_factory(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    @staticmethod
    def _to_omit[T](value: T | None) -> T | Omit:
        return value if value is not None else omit

    def _resolve_prompt_cache_retention(
        self, *, extended_prompt_retention: bool
    ) -> Literal["24h"] | Omit:
        return self._to_omit("24h" if extended_prompt_retention else None)

    @staticmethod
    def _adapt_usage(response: Response) -> LLMTokenUsage | None:
        usage = response.usage
        if usage is None:
            return None
        return LLMTokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.input_tokens_details.cached_tokens,
            total_tokens=usage.total_tokens,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        input = self.adapter.adapt_messages(request.messages)
        model = self.config.model
        parallel_tool_calls = request.options.parallel_tool_calls
        prompt_cache_retention = self._resolve_prompt_cache_retention(
            extended_prompt_retention=request.options.extended_prompt_retention
        )
        temperature = self._to_omit(request.options.temperature)
        tools = self.adapter.adapt_tools(request.tools)
        top_logprobs = self._to_omit(request.options.top_logprobs)
        top_p = self._to_omit(request.options.top_p)
        truncation = self._to_omit(request.options.truncation)

        try:
            response: Response = await self.client.responses.create(
                input=input,
                model=model,
                parallel_tool_calls=parallel_tool_calls,
                prompt_cache_retention=prompt_cache_retention,
                temperature=temperature,
                tools=tools,
                top_logprobs=top_logprobs,
                top_p=top_p,
                truncation=truncation,
            )
            return LLMResponse(
                output=AssistantMessage(
                    content=response.output_text or "",
                    tool_calls=self.adapter.parse_tool_calls(response),
                ),
                usage=self._adapt_usage(response),
            )
        except Exception as e:
            raise_llm_error_from_openai(e, backend="responses")


class ResponsesDriverAdapter(
    LLMAdapter[ResponseInputParam, list[FunctionToolParam] | Omit, Response]
): ...
