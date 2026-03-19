from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import openai
from openai import AsyncOpenAI, Omit, omit
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    Response,
    ResponseFunctionToolCall,
    ResponseInputParam,
    ToolParam,
)
from openai.types.responses.response_function_tool_call_param import ResponseFunctionToolCallParam
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputItemParam

from koda.llm.drivers import ResponsesDriver, ResponsesDriverConfig
from koda.llm.exceptions import (
    ApiKeyNotConfiguredError,
    EmptyApiKeyError,
    InvalidToolCallArgumentsError,
    UnknownMessageTypeError,
)
from koda.llm.models import ModelCapabilities, ModelDefinition, ThinkingOption
from koda.llm.protocols import LLMAdapter
from koda.llm.providers.base import LLMProviderBase
from koda.llm.utils import resolve_openai_client
from koda.messages import AssistantMessage, Message, ToolMessage, UserMessage
from koda.tools import ToolCall, ToolDefinition
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from openai.types.chat.completion_create_params import ReasoningEffort
    from openai.types.shared_params.reasoning import Reasoning

    from koda.llm.models import ThinkingOptionId
    from koda.llm.protocols import LLM
    from koda.llm.registry import ModelRegistry
    from koda.llm.types import LLMRequest, LLMResponse
    from koda_common.settings import SettingsManager

logger = get_logger(__name__)

_OPENAI_THINKING_LOW_TO_XHIGH = [
    ThinkingOption(id="none", label="Off", description="No interleaved thinking."),
    ThinkingOption(id="low", label="Low", description="Low effort for straightforward tasks."),
    ThinkingOption(id="medium", label="Medium", description="Balanced effort for most tasks."),
    ThinkingOption(id="high", label="High", description="High effort for complex tasks."),
    ThinkingOption(id="xhigh", label="XHigh", description="Extra high effort for complex tasks."),
]

_OPENAI_THINKING_LOW_TO_HIGH = [
    ThinkingOption(id="none", label="Off", description="No interleaved thinking."),
    ThinkingOption(id="low", label="Low", description="Low effort for straightforward tasks."),
    ThinkingOption(id="medium", label="Medium", description="Balanced effort for most tasks."),
    ThinkingOption(id="high", label="High", description="High effort for complex tasks."),
]

_OPENAI_REASONING_EFFORTS: dict[ThinkingOptionId, ReasoningEffort] = {
    "none": "none",
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
}

OPENAI_MODELS: Sequence[ModelDefinition] = [
    ModelDefinition(
        id="gpt-5.4",
        name="gpt-5.4",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_XHIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.4-mini",
        name="gpt-5.4-mini",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_XHIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.4-nano",
        name="gpt-5.4-nano",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_XHIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.3-codex",
        name="gpt-5.3-codex",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_XHIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.2-codex",
        name="gpt-5.2-codex",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_XHIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.2",
        name="gpt-5.2",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_XHIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.1-codex",
        name="gpt-5.1-codex",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_HIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5.1",
        name="gpt-5.1",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_HIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5",
        name="gpt-5",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_HIGH,
        capabilities={
            ModelCapabilities.WEB_SEARCH,
            ModelCapabilities.EXTENDED_PROMPT_RETENTION,
        },
    ),
    ModelDefinition(
        id="gpt-5-mini",
        name="gpt-5-mini",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_HIGH,
        capabilities={ModelCapabilities.WEB_SEARCH},
    ),
    ModelDefinition(
        id="gpt-5-nano",
        name="gpt-5-nano",
        provider="openai",
        thinking_options=_OPENAI_THINKING_LOW_TO_HIGH,
        capabilities={ModelCapabilities.WEB_SEARCH},
    ),
]


class OpenAIResponseAdapter(LLMAdapter[ResponseInputParam, list[ToolParam] | Omit, Response]):
    @staticmethod
    def _parse_tool_call_arguments(raw_arguments: str) -> dict[str, Any]:
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as e:
            raise InvalidToolCallArgumentsError from e
        if not isinstance(arguments, dict):
            raise InvalidToolCallArgumentsError
        return arguments

    @staticmethod
    def _to_provider_user_message(message: UserMessage) -> EasyInputMessageParam:
        return EasyInputMessageParam(role="user", content=message.content, type="message")

    @staticmethod
    def _to_provider_tool_message(message: ToolMessage) -> FunctionCallOutput:
        tool_output = message.tool_result.output
        output_data: dict[str, Any] = {
            "content": tool_output.content,
            "is_error": tool_output.is_error,
        }
        if tool_output.error_message:
            output_data["error_message"] = tool_output.error_message
        return FunctionCallOutput(
            call_id=message.tool_result.call_id,
            output=json.dumps(output_data),
            type="function_call_output",
        )

    @staticmethod
    def _to_provider_assistant_message(message: AssistantMessage) -> list[ResponseInputItemParam]:
        result: list[ResponseInputItemParam] = []
        if message.content or not message.tool_calls:
            result.append(
                EasyInputMessageParam(
                    role="assistant",
                    content=message.content,
                    type="message",
                )
            )
        result.extend(
            ResponseFunctionToolCallParam(
                type="function_call",
                name=tool_call.tool_name,
                arguments=json.dumps(tool_call.arguments),
                call_id=tool_call.call_id,
            )
            for tool_call in message.tool_calls
        )
        return result

    def to_provider_messages(self, messages: Sequence[Message]) -> ResponseInputParam:
        result: ResponseInputParam = []
        for message in messages:
            if isinstance(message, UserMessage):
                result.append(self._to_provider_user_message(message))
                continue
            if isinstance(message, ToolMessage):
                result.append(self._to_provider_tool_message(message))
                continue
            if isinstance(message, AssistantMessage):
                result.extend(self._to_provider_assistant_message(message))
                continue
            raise UnknownMessageTypeError(type(message))
        return result

    @staticmethod
    def _to_provider_tool_definition(tool: ToolDefinition) -> FunctionToolParam:
        schema = openai.pydantic_function_tool(
            tool.parameters_model,
            name=tool.name,
            description=tool.description,
        )
        function = schema["function"]
        return FunctionToolParam(
            type="function",
            name=function["name"],
            description=function.get("description"),
            parameters=function["parameters"],
            strict=function.get("strict", True),
        )

    def to_provider_tools(self, tools: Sequence[ToolDefinition] | None) -> list[ToolParam] | Omit:
        if not tools:
            return omit
        return [self._to_provider_tool_definition(tool) for tool in tools]

    def extract_tool_calls(self, response: Response) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for output in response.output:
            if not isinstance(output, ResponseFunctionToolCall):
                continue
            calls.append(
                ToolCall(
                    tool_name=output.name,
                    arguments=self._parse_tool_call_arguments(output.arguments),
                    call_id=output.call_id,
                )
            )
        return calls


@dataclass(frozen=True, slots=True)
class OpenAILLMProviderConfig:
    api_key: str
    model: str
    base_url: str | None = None


class OpenAILLMProvider(LLMProviderBase):
    provider_name: str = "openai"

    @staticmethod
    def _resolve_reasoning(reasoning: ThinkingOptionId) -> Reasoning | Omit:
        effort = _OPENAI_REASONING_EFFORTS[reasoning]
        return {"effort": effort, "summary": "auto"}

    def __init__(
        self,
        driver: ResponsesDriver,
        *,
        model_definition: ModelDefinition,
    ) -> None:
        super().__init__(driver=driver)
        self.model = model_definition.id
        self.capabilities = set(model_definition.capabilities)

    @classmethod
    def from_config(
        cls,
        config: OpenAILLMProviderConfig,
        *,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
        model_registry: ModelRegistry,
    ) -> OpenAILLMProvider:
        api_key = config.api_key.strip()
        if not api_key:
            raise EmptyApiKeyError(cls.provider_name)

        model_definition = model_registry.get(cls.provider_name, config.model)
        driver_config = ResponsesDriverConfig(
            api_key=api_key,
            model=model_definition.id,
            base_url=config.base_url,
        )
        driver = ResponsesDriver(
            config=driver_config,
            adapter=OpenAIResponseAdapter(),
            reasoning_resolver=cls._resolve_reasoning,
            client_factory=client_factory,
        )
        return cls(
            driver=driver,
            model_definition=model_definition,
        )

    @staticmethod
    def _apply_capabilities(
        request: LLMRequest,
        *,
        capabilities: set[ModelCapabilities],
    ) -> LLMRequest:
        resolved_options = replace(
            request.options,
            web_search=(
                request.options.web_search and ModelCapabilities.WEB_SEARCH in capabilities
            ),
            extended_prompt_retention=(
                request.options.extended_prompt_retention
                and ModelCapabilities.EXTENDED_PROMPT_RETENTION in capabilities
            ),
        )
        return replace(request, options=resolved_options)

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        resolved_request = self._apply_capabilities(
            request,
            capabilities=self.capabilities,
        )
        return await self.driver.generate(resolved_request)

    def generate_stream(self, request: LLMRequest):
        resolved_request = self._apply_capabilities(
            request,
            capabilities=self.capabilities,
        )
        return self.driver.generate_stream(resolved_request)


def create_openai_llm(settings: SettingsManager, model_registry: ModelRegistry) -> LLM:
    provider = OpenAILLMProvider.provider_name
    api_key = settings.get_api_key(provider)
    if api_key is None:
        raise ApiKeyNotConfiguredError(provider)
    config = OpenAILLMProviderConfig(api_key=api_key, model=settings.model)
    client_factory = resolve_openai_client(settings)
    return OpenAILLMProvider.from_config(
        config,
        client_factory=client_factory,
        model_registry=model_registry,
    )
