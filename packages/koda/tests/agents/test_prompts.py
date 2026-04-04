from __future__ import annotations

import pytest

from koda.agents.prompts import (
    BEHAVIOR_PROMPT,
    ENVIRONMENT_PROMPT,
    IDENTITY_PROMPT,
    PromptContext,
    PromptContextRequiredError,
    PromptSection,
    PromptVariableMissingError,
    SystemPrompt,
    render_prompt,
)


def test_render_prompt_renders_default_sections_in_order() -> None:
    prompt = SystemPrompt()
    context = PromptContext(variables={"model": "GPT-5.4", "provider": "openai"})

    assert render_prompt(prompt, context) == "\n\n".join(
        [
            IDENTITY_PROMPT,
            ENVIRONMENT_PROMPT,
            BEHAVIOR_PROMPT,
        ]
    )


def test_render_prompt_omits_blank_sections() -> None:
    prompt = SystemPrompt(
        sections=(
            PromptSection(name="identity", content="  "),
            PromptSection(name="custom", content="Extra guidance"),
            PromptSection(name="blank", content="\n"),
        )
    )

    assert render_prompt(prompt) == "Extra guidance"


def test_render_prompt_raises_for_template_without_context() -> None:
    prompt = SystemPrompt(
        sections=(PromptSection(name="environment", content="Model: {model}", template=True),)
    )

    with pytest.raises(PromptContextRequiredError, match="requires a prompt context"):
        render_prompt(prompt)


def test_render_prompt_raises_for_missing_context_variable() -> None:
    prompt = SystemPrompt(
        sections=(PromptSection(name="client", content="Client: {client_name}", template=True),)
    )
    context = PromptContext(variables={"model": "GPT-5.4", "provider": "openai"})

    with pytest.raises(PromptVariableMissingError, match="client_name"):
        render_prompt(prompt, context)


def test_system_prompt_section_mutators_preserve_order() -> None:
    prompt = (
        SystemPrompt()
        .upsert_sections(PromptSection(name="environment", content="Model: {model}", template=True))
        .append_sections(PromptSection(name="tui", content="Use concise terminal language"))
        .remove_sections("behavior")
    )
    context = PromptContext(variables={"model": "GPT-5.4", "provider": "openai"})

    assert render_prompt(prompt, context) == "\n\n".join(
        [
            IDENTITY_PROMPT,
            "Model: GPT-5.4",
            "Use concise terminal language",
        ]
    )


def test_render_prompt_returns_override_as_is() -> None:
    prompt = SystemPrompt(override="  literal override  ")

    assert render_prompt(prompt) == "  literal override  "
