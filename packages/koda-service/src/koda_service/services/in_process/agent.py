from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.agents import Agent, AgentConfig, PromptContext, SystemPrompt
from koda.llm import LLMRequestOptions, ModelRegistry, ProviderRegistry
from koda.llm.providers import BERGETAI_MODELS
from koda.llm.providers.bergetai import BERGETAI_PROVIDER, create_bergetai_llm
from koda.llm.providers.openai import OPENAI_MODELS, OPENAI_PROVIDER, create_openai_llm
from koda.tools import FileCoordinator, ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda.tools.policy import ToolPolicy

if TYPE_CHECKING:
    from pathlib import Path

    from koda.sessions import SessionManager
    from koda_common.settings import SettingsManager


def build_registries() -> tuple[ModelRegistry, ProviderRegistry]:
    """Build the default provider and model registries."""
    model_registry = ModelRegistry()
    model_registry.register_all(OPENAI_MODELS)
    model_registry.register_all(BERGETAI_MODELS)

    provider_registry = ProviderRegistry()
    provider_registry.register(OPENAI_PROVIDER, create_openai_llm)
    provider_registry.register(BERGETAI_PROVIDER, create_bergetai_llm)

    return model_registry, provider_registry


def build_tools(*, sandbox_dir: Path, cwd: Path) -> ToolConfig:
    """Build the default tool configuration."""
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    context = ToolContext(
        cwd=cwd.resolve(),
        policy=ToolPolicy.create(sandbox_dir=sandbox_dir.resolve()),
        files=FileCoordinator(),
    )
    return ToolConfig(registry=registry, context=context)


@dataclass(frozen=True, slots=True)
class InProcessAgentConfig:
    """Configuration for building the in-process Koda agent."""

    cwd: Path
    system_prompt: SystemPrompt = field(default_factory=SystemPrompt)
    prompt_context: PromptContext | None = None
    max_tool_iterations: int = 30
    tools: ToolConfig | None = None

    def build(
        self,
        settings: SettingsManager,
        session_manager: SessionManager,
        *,
        sandbox_dir: Path,
    ) -> Agent:
        """Create the Koda agent for the current settings and session state."""
        model_registry, provider_registry = build_registries()
        llm = provider_registry.create(settings.provider, settings, model_registry)
        tools = self.tools or build_tools(sandbox_dir=sandbox_dir, cwd=self.cwd)
        config = AgentConfig(
            system_prompt=self.system_prompt,
            prompt_context=self.prompt_context,
            request_options=LLMRequestOptions(
                thinking=settings.thinking,
                web_search=settings.allow_web_search,
                extended_prompt_retention=settings.allow_extended_prompt_retention,
            ),
            max_tool_iterations=self.max_tool_iterations,
        )
        return Agent(
            llm=llm,
            config=config,
            session_manager=session_manager,
            tools=tools,
        )
