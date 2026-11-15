from __future__ import annotations

from koda.agent import AgentSettings
from koda.llm import Model, Thinking, ThinkingOption


def _model() -> Model:
    return Model(
        id="m",
        name="M",
        provider="p",
        thinking=Thinking((ThinkingOption("low", "Low"), ThinkingOption("high", "High"))),
    )


def test_request_options_carry_the_settings() -> None:
    settings = AgentSettings(thinking="high", web_search=True, extended_prompt_retention=True)

    options = settings.request_options(_model())

    assert (options.thinking, options.web_search, options.extended_prompt_retention) == (
        "high",
        True,
        True,
    )


def test_thinking_the_model_lacks_falls_back_to_its_first_level() -> None:
    assert AgentSettings(thinking="max").request_options(_model()).thinking == "low"
