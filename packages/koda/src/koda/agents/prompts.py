from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

IDENTITY_PROMPT: Final[str] = (
    "You are Koda, an expert coding assistant built to help the user "
    "navigate, understand, and modify codebases."
)
ENVIRONMENT_PROMPT: Final[str] = "You are currently powered by {model} running via {provider}."
BEHAVIOR_PROMPT: Final[str] = (
    "Be clear, practical, and concise. "
    "Prefer concrete next steps and implementation details when helpful.\n\n"
    "When working with code, preserve the user's intent, avoid unnecessary changes, "
    "and call out important assumptions or risks."
)


class PromptRenderError(Exception):
    """Base error raised when a prompt cannot be rendered."""


class PromptContextRequiredError(PromptRenderError):
    def __init__(self, section_name: str) -> None:
        super().__init__(f"Prompt section '{section_name}' requires a prompt context")


class PromptVariableMissingError(PromptRenderError):
    def __init__(self, section_name: str, variable_name: str) -> None:
        super().__init__(
            f"Prompt section '{section_name}' requires context variable '{variable_name}'"
        )


def _normalize(text: str | None) -> str | None:
    if text is None:
        return None
    normalized = text.strip()
    return normalized or None


@dataclass(frozen=True, slots=True)
class PromptContext:
    """Dynamic values available when rendering prompt templates."""

    model: str | None = None
    provider: str | None = None
    variables: Mapping[str, object] = field(default_factory=dict)

    def format_kwargs(self) -> dict[str, object]:
        kwargs = dict(self.variables)
        if self.model is not None:
            kwargs["model"] = self.model
        if self.provider is not None:
            kwargs["provider"] = self.provider
        return kwargs


@dataclass(frozen=True, slots=True)
class PromptSection:
    """A named prompt section rendered in order."""

    name: str
    content: str | None
    template: bool = False


def _default_sections() -> tuple[PromptSection, ...]:
    return (
        PromptSection(name="identity", content=IDENTITY_PROMPT),
        PromptSection(name="environment", content=ENVIRONMENT_PROMPT, template=True),
        PromptSection(name="behavior", content=BEHAVIOR_PROMPT),
    )


@dataclass(frozen=True, slots=True)
class SystemPrompt:
    """Composable immutable system prompt.

    Prompt behavior comes from ordered sections, not hard-coded top-level fields.
    That keeps the core model stable as new prompt features are added.

    `override` bypasses normal section rendering entirely and is returned as-is.
    """

    sections: tuple[PromptSection, ...] = field(default_factory=_default_sections)
    override: str | None = None

    def append_sections(self, *sections: PromptSection) -> SystemPrompt:
        return replace(self, sections=self.sections + tuple(sections))

    def upsert_sections(self, *sections: PromptSection) -> SystemPrompt:
        replacements = {section.name: section for section in sections}
        updated = [replacements.pop(section.name, section) for section in self.sections]
        updated.extend(replacements.values())
        return replace(self, sections=tuple(updated))

    def remove_sections(self, *names: str) -> SystemPrompt:
        removed = set(names)
        return replace(
            self,
            sections=tuple(section for section in self.sections if section.name not in removed),
        )


def _render_section(section: PromptSection, context: PromptContext | None) -> str | None:
    text = _normalize(section.content)
    if text is None:
        return None
    if not section.template:
        return text
    if context is None:
        raise PromptContextRequiredError(section.name)
    try:
        return _normalize(text.format(**context.format_kwargs()))
    except KeyError as error:
        variable_name = error.args[0]
        raise PromptVariableMissingError(section.name, str(variable_name)) from error


def render_prompt(prompt: SystemPrompt, context: PromptContext | None = None) -> str | None:
    """Render a system prompt into its final string form.

    Returns the prompt override when one is set. Otherwise, renders each section,
    drops sections whose normalized content is empty, and joins the remaining
    section texts with blank lines. Returns ``None`` when no section produces
    content.

    Args:
        prompt: The prompt definition to render.
        context: Optional values used to fill template variables in templated
            sections.

    Returns:
        The fully rendered prompt string, or ``None`` if the prompt renders to no
        content.

    Raises:
        PromptContextRequiredError: If a section is marked as templated but no
            ``context`` is provided.
        PromptVariableMissingError: If a templated section references a variable
            that is not available in ``context``.
    """

    if prompt.override is not None:
        return prompt.override

    parts = [
        text
        for section in prompt.sections
        if (text := _render_section(section, context)) is not None
    ]
    return "\n\n".join(parts) or None
