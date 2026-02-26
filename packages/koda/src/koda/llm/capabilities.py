from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Protocol

from koda.llm.models import ModelCapabilities, ModelDefinition
from koda.llm.protocols import LLM

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.llm import LLMEvent, LLMResponse
    from koda.llm.types import LLMRequest
    from koda.messages import AssistantMessage


class CapabilityResolver(Protocol):
    def apply(
        self,
        *,
        provider: str,
        model: str,
        request: LLMRequest,
    ) -> LLMRequest: ...


def apply_capabilities(
    request: LLMRequest,
    *,
    capabilities: set[ModelCapabilities],
) -> LLMRequest:
    resolved_options = replace(
        request.options,
        web_search=(request.options.web_search and ModelCapabilities.WEB_SEARCH in capabilities),
        extended_prompt_retention=(
            request.options.extended_prompt_retention
            and ModelCapabilities.EXTENDED_PROMPT_RETENTION in capabilities
        ),
    )
    return replace(request, options=resolved_options)


class StaticCapabilityResolver:
    def __init__(self, model_definitions: list[ModelDefinition]) -> None:
        self._capabilities_by_provider_model: dict[tuple[str, str], set[ModelCapabilities]] = {
            (
                definition.provider.strip().lower(),
                definition.id.strip().lower(),
            ): set(definition.capabilities)
            for definition in model_definitions
        }

    def apply(
        self,
        *,
        provider: str,
        model: str,
        request: LLMRequest,
    ) -> LLMRequest:
        capabilities = self._capabilities_by_provider_model.get(
            (provider.strip().lower(), model.strip().lower()),
            set(),
        )
        return apply_capabilities(request, capabilities=capabilities)


class CapabilityResolvedLLM(LLM):
    def __init__(
        self,
        *,
        driver: LLM,
        resolver: CapabilityResolver,
        provider: str,
        model: str,
    ) -> None:
        self._driver = driver
        self._resolver = resolver
        self._provider = provider
        self._model = model

    def _resolve_request(self, request: LLMRequest) -> LLMRequest:
        return self._resolver.apply(
            provider=self._provider,
            model=self._model,
            request=request,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        return await self._driver.generate(self._resolve_request(request))

    def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        return self._driver.generate_stream(self._resolve_request(request))
