"""An interruption reaches every API as a user message the model can read."""

from __future__ import annotations

from typing import Any

import pytest

from koda.llm.apis.completions import OpenAICompletionsAdapter
from koda.llm.apis.messages import AnthropicMessagesAdapter
from koda.llm.apis.responses import OpenAIResponsesAdapter
from koda.messages import InterruptionMessage


@pytest.mark.parametrize(
    "adapter",
    [OpenAICompletionsAdapter(), OpenAIResponsesAdapter(), AnthropicMessagesAdapter()],
)
def test_an_interruption_is_sent_as_user_text(adapter: Any) -> None:
    [message] = adapter.to_provider_messages([InterruptionMessage()])

    assert message["role"] == "user"
    assert message["content"] == InterruptionMessage().content
