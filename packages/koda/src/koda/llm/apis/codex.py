from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import exceptions
from koda.llm.apis.credentials import resolve_oauth_credential
from koda.llm.apis.responses import (
    OpenAIResponsesAdapter,
    OpenAIResponsesAPI,
    OpenAIResponsesAPIConfig,
    OpenAIResponsesEventAdapter,
)
from koda.llm.utils import resolve_openai_client
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from koda.llm.apis.base import LLMApiContext

log = get_logger(__name__)

CODEX_ORIGINATOR = "koda"
CODEX_BACKEND = "openai-codex-responses"
CODEX_ACCOUNT_ID_METADATA_KEY = "chatgpt_account_id"


class OpenAICodexResponsesAPI(OpenAIResponsesAPI):
    """Concrete LLM implementation backed by ChatGPT Codex Responses."""

    @classmethod
    def from_context(cls, context: LLMApiContext) -> OpenAICodexResponsesAPI:
        """Create a Codex Responses API from a resolved model-catalog context."""
        credential = resolve_oauth_credential(context)
        account_id = credential.metadata.get(CODEX_ACCOUNT_ID_METADATA_KEY)
        if not account_id:
            raise exceptions.OAuthAccountIdMissingError(context.provider_id)

        capabilities = (
            context.provider.capabilities
            | context.connection.capabilities
            | context.model.capabilities
        )
        config = OpenAIResponsesAPIConfig(
            api_key=credential.access_token,
            base_url=context.connection.base_url,
            model=context.model.id,
            backend=CODEX_BACKEND,
            web_search=bool(capabilities.get("web_search", False)),
            extended_prompt_retention=bool(capabilities.get("extended_prompt_retention", False)),
            prompt_cache_retention_supported=False,
            truncation_supported=False,
            store=False,
        )
        log.info(
            "codex_api_from_context",
            base_url=config.base_url,
            model=config.model,
            account_id=account_id,
            backend=config.backend,
        )
        client_factory = resolve_openai_client(context.settings)
        return cls(
            config,
            client=client_factory(
                api_key=config.api_key,
                base_url=config.base_url,
                default_headers={
                    "chatgpt-account-id": account_id,
                    "originator": CODEX_ORIGINATOR,
                },
            ),
            adapter=OpenAIResponsesAdapter(),
            event_adapter=OpenAIResponsesEventAdapter(),
        )
