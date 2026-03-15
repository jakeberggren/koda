from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI, Omit, omit
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_assistant_message_param import (
    ChatCompletionAssistantMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_message_function_tool_call_param import (
    ChatCompletionMessageFunctionToolCallParam,
)
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_message_param import ChatCompletionToolMessageParam
from openai.types.chat.chat_completion_tool_union_param import ChatCompletionToolUnionParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam

from koda.llm.drivers import CompletionsDriver, CompletionsDriverConfig
from koda.llm.exceptions import (
    ApiKeyNotConfiguredError,
    EmptyApiKeyError,
    InvalidToolCallArgumentsError,
    UnknownMessageTypeError,
)
from koda.llm.models import ModelDefinition
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.providers.base import LLMProviderBase
from koda.llm.utils import resolve_openai_client
from koda.messages import AssistantMessage, Message, ToolMessage, UserMessage
from koda.tools import ToolCall, ToolDefinition

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from koda.llm.models import ThinkingOptionId
    from koda.llm.registry import ModelRegistry
    from koda.llm.types import LLMRequest, LLMResponse
    from koda_common.settings import SettingsManager

BERGETAI_BASE_URL = "https://api.berget.ai/v1"

BERGETAI_MODELS: Sequence[ModelDefinition] = [
    ModelDefinition(
        id="zai-org/GLM-4.7",
        name="GLM-4.7",
        provider="bergetai",
    ),
    ModelDefinition(
        id="openai/gpt-oss-120b",
        name="gpt-oss-120b",
        provider="bergetai",
    ),
    ModelDefinition(
        id="mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        name="Mistral-Small-3.2-24B-Instruct-2506",
        provider="bergetai",
    ),
    ModelDefinition(
        id="meta-llama/Llama-3.1-8B-Instruct",
        name="Llama-3.1-8B-Instruct",
        provider="bergetai",
    ),
    ModelDefinition(
        id="meta-llama/Llama-3.3-70B-Instruct",
        name="Llama-3.3-70B-Instruct",
        provider="bergetai",
    ),
]


class BergetAICompletionsAdapter(
    LLMAdapter[
        list[ChatCompletionMessageParam],
        list[ChatCompletionToolUnionParam] | Omit,
        ChatCompletion,
    ]
):
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
    def _to_provider_tool_message(message: ToolMessage) -> ChatCompletionToolMessageParam:
        tool_output = message.tool_result.output
        payload: dict[str, Any] = {
            "content": tool_output.content,
            "is_error": tool_output.is_error,
        }
        if tool_output.error_message:
            payload["error_message"] = tool_output.error_message

        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=message.tool_result.call_id,
            content=json.dumps(payload),
        )

    @staticmethod
    def _to_provider_user_message(message: UserMessage) -> ChatCompletionUserMessageParam:
        return ChatCompletionUserMessageParam(role="user", content=message.content)

    @staticmethod
    def _to_provider_assistant_message(
        message: AssistantMessage,
    ) -> ChatCompletionAssistantMessageParam:
        if message.tool_calls:
            tool_calls = [
                ChatCompletionMessageFunctionToolCallParam(
                    id=tool_call.call_id,
                    type="function",
                    function={
                        "name": tool_call.tool_name,
                        "arguments": json.dumps(tool_call.arguments),
                    },
                )
                for tool_call in message.tool_calls
            ]
            return ChatCompletionAssistantMessageParam(
                role="assistant",
                content=message.content,
                tool_calls=tool_calls,
            )
        return ChatCompletionAssistantMessageParam(role="assistant", content=message.content)

    def to_provider_messages(self, messages: Sequence[Message]) -> list[ChatCompletionMessageParam]:
        result: list[ChatCompletionMessageParam] = []
        for message in messages:
            if isinstance(message, ToolMessage):
                result.append(self._to_provider_tool_message(message))
                continue
            if isinstance(message, UserMessage):
                result.append(self._to_provider_user_message(message))
                continue
            if isinstance(message, AssistantMessage):
                result.append(self._to_provider_assistant_message(message))
                continue
            raise UnknownMessageTypeError(type(message))
        return result

    @staticmethod
    def _remove_null_type_from_anyof(options: list[Any]) -> list[Any]:
        return [
            option
            for option in options
            if not (isinstance(option, dict) and option.get("type") == "null")
        ]

    def _merge_single_anyof_object(
        self,
        result: dict[str, Any],
        options: list[Any],
    ) -> bool:
        if len(options) != 1 or not isinstance(options[0], dict):
            return False
        inner = self._simplify_schema(options[0])
        if not isinstance(inner, dict):
            return False
        for inner_key, inner_value in inner.items():
            if inner_key not in result:
                result[inner_key] = inner_value
        return True

    def _simplify_schema_dict(self, value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, raw in value.items():
            if key == "$schema":
                continue
            if key == "anyOf" and isinstance(raw, list):
                non_null = self._remove_null_type_from_anyof(raw)
                if self._merge_single_anyof_object(result, non_null):
                    continue
                result[key] = self._simplify_schema(non_null if non_null else raw)
                continue
            result[key] = self._simplify_schema(raw)
        return result

    def _simplify_schema(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._simplify_schema(item) for item in value]
        if isinstance(value, dict):
            return self._simplify_schema_dict(value)
        return value

    def _to_provider_tool_definition(self, tool: ToolDefinition) -> ChatCompletionToolUnionParam:
        schema = self._simplify_schema(tool.parameters_model.model_json_schema())
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "strict": True,
                "parameters": schema,
            },
        }

    def to_provider_tools(
        self,
        tools: Sequence[ToolDefinition] | None,
    ) -> list[ChatCompletionToolUnionParam] | Omit:
        if not tools:
            return omit
        return [self._to_provider_tool_definition(tool) for tool in tools]

    def extract_tool_calls(self, response: ChatCompletion) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for choice in response.choices:
            for tool_call in choice.message.tool_calls or ():
                if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                    continue
                calls.append(
                    ToolCall(
                        tool_name=tool_call.function.name,
                        arguments=self._parse_tool_call_arguments(tool_call.function.arguments),
                        call_id=tool_call.id,
                    )
                )
        return calls


@dataclass(frozen=True, slots=True)
class BergetAILLMProviderConfig:
    api_key: str
    model: str
    base_url: str | None = BERGETAI_BASE_URL


class BergetAILLMProvider(LLMProviderBase):
    provider_name: str = "bergetai"

    @staticmethod
    def _resolve_reasoning(reasoning: ThinkingOptionId) -> Omit:
        _ = reasoning
        # The OpenAI-compatible chat-completions path does not expose visible reasoning
        # output, and Berget's docs are unclear about completions-side reasoning support,
        # so KODA does not advertise or forward thinking controls for BergetAI here.
        return omit

    def __init__(
        self,
        driver: CompletionsDriver,
        *,
        model_definition: ModelDefinition,
    ) -> None:
        super().__init__(driver=driver)
        self.model = model_definition.id

    @classmethod
    def from_config(
        cls,
        config: BergetAILLMProviderConfig,
        *,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
        model_registry: ModelRegistry,
    ) -> BergetAILLMProvider:
        api_key = config.api_key.strip()
        if not api_key:
            raise EmptyApiKeyError(cls.provider_name)

        model_definition = model_registry.get(cls.provider_name, config.model)
        driver_config = CompletionsDriverConfig(
            api_key=api_key,
            model=model_definition.id,
            base_url=config.base_url,
        )
        driver = CompletionsDriver(
            config=driver_config,
            adapter=BergetAICompletionsAdapter(),
            reasoning_resolver=cls._resolve_reasoning,
            client_factory=client_factory,
        )
        return cls(
            driver=driver,
            model_definition=model_definition,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        return await self.driver.generate(request)

    def generate_stream(self, request: LLMRequest):
        return self.driver.generate_stream(request)


def create_bergetai_llm(settings: SettingsManager, model_registry: ModelRegistry) -> LLM:
    provider = BergetAILLMProvider.provider_name
    api_key = settings.get_api_key(provider)
    if api_key is None:
        raise ApiKeyNotConfiguredError(provider)
    config = BergetAILLMProviderConfig(api_key=api_key, model=settings.model)
    client_factory = resolve_openai_client(settings)
    return BergetAILLMProvider.from_config(
        config,
        client_factory=client_factory,
        model_registry=model_registry,
    )
