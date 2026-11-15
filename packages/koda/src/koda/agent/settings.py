"""Agent settings: the model an agent uses, and how it asks it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from koda.llm import LLMRequestOptions, ThinkingOptionId

if TYPE_CHECKING:
    from koda.llm import Model


class AgentSettings(BaseModel):
    """What the user picked for the agent. Changed by replacing it:
    ``copy.replace(settings, ...)``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = None
    model: str | None = None
    thinking: ThinkingOptionId = "none"
    web_search: bool = False
    extended_prompt_retention: bool = False

    def request_options(self, model: Model) -> LLMRequestOptions:
        """The options to ask ``model`` with: the thinking level it supports nearest
        the one picked."""
        return LLMRequestOptions(
            thinking=model.thinking.resolve(self.thinking).id,
            web_search=self.web_search,
            extended_prompt_retention=self.extended_prompt_retention,
        )
