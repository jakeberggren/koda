from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda.llm.apis.completions import OpenAICompletionsAPI
from koda.llm.apis.messages import AnthropicMessagesAPI
from koda.llm.apis.responses import OpenAIResponsesAPI

if TYPE_CHECKING:
    from collections.abc import Mapping

    from koda.llm.apis.base import LLMApiFactory


def _normalize(value: str) -> str:
    return value.strip().lower()


class LLMApiRegistry:
    """Registry mapping model-catalog API ids to concrete LLM constructors."""

    @classmethod
    def default(cls) -> LLMApiRegistry:
        """Build the registry containing Koda's built-in API implementations."""
        return cls(
            {
                "anthropic-messages": AnthropicMessagesAPI.from_context,
                "openai-completions": OpenAICompletionsAPI.from_context,
                "openai-responses": OpenAIResponsesAPI.from_context,
            }
        )

    def __init__(self, apis: Mapping[str, LLMApiFactory] | None = None) -> None:
        """Create a registry from API ids and their constructors."""
        self._apis: dict[str, LLMApiFactory] = {}
        for api_id, api in (apis or {}).items():
            self.register(api_id, api)

    def register(self, api_id: str, api: LLMApiFactory) -> None:
        """Register an API constructor under a case-insensitive id."""
        normalized_api_id = _normalize(api_id)
        if not normalized_api_id:
            raise exceptions.ApiNameEmptyError
        if normalized_api_id in self._apis:
            raise exceptions.ApiAlreadyRegisteredError(normalized_api_id)
        self._apis[normalized_api_id] = api

    def get(self, api_id: str) -> LLMApiFactory:
        """Return the registered constructor for an API id."""
        normalized_api_id = _normalize(api_id)
        api = self._apis.get(normalized_api_id)
        if api is None:
            raise exceptions.ApiNotSupportedError(api_id)
        return api
