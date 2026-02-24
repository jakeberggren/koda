from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from openai import AsyncOpenAI, Omit
from openai.types.responses import FunctionToolParam, Response, ResponseInputParam

from koda.llm.protocols import LLM, LLMAdapter
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ResponsesDriverConfig:
    api_key: str
    model: str
    base_url: str | None = None
    allow_extended_prompt_retention: bool = False
    enable_web_search: bool = False
    parallel_tool_calls: bool = True


class ResponsesDriver(LLM):
    def __init__(
        self,
        config: ResponsesDriverConfig,
        *,
        adapter: ResponsesDriverAdapter | None = None,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
        error_handler: Callable[[Exception], NoReturn] | None = None,
    ) -> None: ...


class ResponsesDriverAdapter(
    LLMAdapter[ResponseInputParam, list[FunctionToolParam] | Omit, Response]
): ...
