from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.agents import Agent, AgentConfig
from koda.llm import LLMRequestOptions
from koda.llm.providers import BERGETAI_MODELS
from koda.llm.providers.bergetai import create_bergetai_llm
from koda.llm.providers.openai import OPENAI_MODELS, create_openai_llm
from koda.llm.registry import ModelRegistry, ProviderRegistry
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools

if TYPE_CHECKING:
    from pathlib import Path

    from koda.sessions import SessionManager
    from koda_common.settings import SettingsManager


@dataclass(frozen=True, slots=True)
class Registries:
    model_registry: ModelRegistry
    provider_registry: ProviderRegistry


def create_model_registry() -> ModelRegistry:
    model_registry = ModelRegistry()
    model_registry.register_all(OPENAI_MODELS)
    model_registry.register_all(BERGETAI_MODELS)
    return model_registry


def create_provider_registry() -> ProviderRegistry:
    provider_registry = ProviderRegistry()
    provider_registry.register("openai", create_openai_llm)
    provider_registry.register("bergetai", create_bergetai_llm)
    return provider_registry


def create_registries() -> Registries:
    return Registries(
        model_registry=create_model_registry(),
        provider_registry=create_provider_registry(),
    )


def create_tool_config(sandbox_dir: Path) -> ToolConfig:
    tool_registry = ToolRegistry()
    tool_registry.register_all(get_builtin_tools())
    tool_context = ToolContext.default(sandbox_dir=sandbox_dir)
    return ToolConfig(registry=tool_registry, context=tool_context)


def create_agent(
    *,
    settings: SettingsManager,
    sandbox_dir: Path,
    session_manager: SessionManager,
    registries: Registries,
    system_message: str | None = None,
) -> Agent:
    llm = registries.provider_registry.create(
        settings.provider,
        settings,
        registries.model_registry,
    )
    request_options = LLMRequestOptions(
        thinking=settings.thinking,
        web_search=settings.allow_web_search,
        extended_prompt_retention=settings.allow_extended_prompt_retention,
    )
    agent_config = AgentConfig(
        system_message=system_message,
        request_options=request_options,
    )
    return Agent(
        llm=llm,
        session_manager=session_manager,
        config=agent_config,
        tools=create_tool_config(sandbox_dir),
    )
