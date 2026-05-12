from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest
from openai.types.chat import ChatCompletion

from koda.llm.apis.completions import (
    OpenAICompletionsAdapter,
    OpenAICompletionsAPI,
    OpenAICompletionsAPIConfig,
    OpenAICompletionsEventAdapter,
)
from koda.llm.types import LLMRequest
from koda.messages import UserMessage

if TYPE_CHECKING:
    from openai import AsyncOpenAI


class _FakeChatCompletionsAPI:
    def __init__(self, response: ChatCompletion) -> None:
        self.response = response
        self.create_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: object) -> ChatCompletion:
        self.create_kwargs = dict(kwargs)
        return self.response


class _FakeChatAPI:
    def __init__(self, response: ChatCompletion) -> None:
        self.completions = _FakeChatCompletionsAPI(response)


class _FakeClient:
    def __init__(self, response: ChatCompletion) -> None:
        self.chat = _FakeChatAPI(response)


def _completion_with_tool_call() -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl_1",
            "created": 0,
            "model": "google/gemma-4-31B-it",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": '{"path": "foo.py"}',
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }
    )


def _api(client: _FakeClient) -> OpenAICompletionsAPI:
    return OpenAICompletionsAPI(
        OpenAICompletionsAPIConfig(
            api_key="test-key",
            base_url="https://api.berget.ai/v1",
            model="google/gemma-4-31B-it",
        ),
        client=cast("AsyncOpenAI", client),
        adapter=OpenAICompletionsAdapter(),
        event_adapter=OpenAICompletionsEventAdapter(),
    )


@pytest.mark.asyncio
async def test_generate_adapts_function_tool_calls() -> None:
    client = _FakeClient(_completion_with_tool_call())
    response = await _api(client).generate(
        LLMRequest(messages=[UserMessage(content="read foo.py")])
    )

    assert response.output.tool_calls[0].tool_name == "read_file"
    assert response.output.tool_calls[0].arguments == {"path": "foo.py"}
    assert response.usage is not None
    assert response.usage.total_tokens == 3
    assert client.chat.completions.create_kwargs is not None
    assert client.chat.completions.create_kwargs["model"] == "google/gemma-4-31B-it"
