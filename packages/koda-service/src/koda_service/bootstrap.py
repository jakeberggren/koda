from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.agents import Agent, AgentConfig, PromptContext, SystemPrompt
from koda.llm import LLMRequestOptions
from koda.llm.providers import BERGETAI_MODELS
from koda.llm.providers.bergetai import BERGETAI_PROVIDER, create_bergetai_llm
from koda.llm.providers.openai import OPENAI_MODELS, OPENAI_PROVIDER, create_openai_llm
from koda.llm.registry import ModelRegistry, ProviderRegistry
from koda.sessions import JsonSessionStore, SessionManager
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda_service.services.in_process.runtime import InProcessRuntimeFactory

if TYPE_CHECKING:
    from pathlib import Path

    from koda_common.settings import SettingsManager


@dataclass(frozen=True, slots=True)
class Registries:
    model_registry: ModelRegistry
    provider_registry: ProviderRegistry


@dataclass(frozen=True, slots=True)
class PromptOverrides:
    system_prompt: SystemPrompt | None = None
    prompt_context: PromptContext | None = None


def create_model_registry() -> ModelRegistry:
    model_registry = ModelRegistry()
    model_registry.register_all(OPENAI_MODELS)
    model_registry.register_all(BERGETAI_MODELS)
    return model_registry


def create_provider_registry() -> ProviderRegistry:
    provider_registry = ProviderRegistry()
    provider_registry.register(OPENAI_PROVIDER, create_openai_llm)
    provider_registry.register(BERGETAI_PROVIDER, create_bergetai_llm)
    return provider_registry


def create_registries() -> Registries:
    return Registries(
        model_registry=create_model_registry(),
        provider_registry=create_provider_registry(),
    )


def create_tool_config(sandbox_dir: Path) -> ToolConfig:
    tool_registry = ToolRegistry()
    tool_registry.register_all(get_builtin_tools())
    tool_context = ToolContext.default(sandbox_dir=sandbox_dir, cwd=sandbox_dir)
    return ToolConfig(registry=tool_registry, context=tool_context)


def create_agent(
    *,
    settings: SettingsManager,
    sandbox_dir: Path,
    session_manager: SessionManager,
    registries: Registries,
    prompt_overrides: PromptOverrides | None = None,
) -> Agent:
    llm = registries.provider_registry.create(
        settings.provider,
        settings,
        registries.model_registry,
    )

    prompt_overrides = prompt_overrides or PromptOverrides()

    request_options = LLMRequestOptions(
        thinking=settings.thinking,
        web_search=settings.allow_web_search,
        extended_prompt_retention=settings.allow_extended_prompt_retention,
    )

    agent_config = AgentConfig(
        system_prompt=prompt_overrides.system_prompt or SystemPrompt(),
        prompt_context=prompt_overrides.prompt_context,
        request_options=request_options,
    )

    return Agent(
        llm=llm,
        session_manager=session_manager,
        config=agent_config,
        tools=create_tool_config(sandbox_dir),
    )


def create_in_process_runtime_factory(
    *,
    settings: SettingsManager,
    sandbox_dir: Path,
    registries: Registries,
    create_agent=create_agent,
    prompt_overrides: PromptOverrides | None = None,
) -> InProcessRuntimeFactory:
    session_manager = SessionManager(JsonSessionStore())
    session_manager.create_session()
    return InProcessRuntimeFactory(
        settings=settings,
        sandbox_dir=sandbox_dir,
        session_manager=session_manager,
        registries=registries,
        create_agent=create_agent,
        prompt_overrides=prompt_overrides,
    )
