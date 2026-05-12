from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.agents import Agent, AgentConfig, PromptContext, SystemPrompt
from koda.execution import create_command_executor
from koda.llm import LLMRequestOptions
from koda.tools import (
    ToolConfig,
    ToolContext,
    ToolExecutionCoordinator,
    ToolRegistry,
    get_builtin_tools,
)
from koda.tools.policy import ToolPolicy

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm import LLM
    from koda.sessions import SessionManager
    from koda_common.settings import SettingsManager


def build_tools(*, sandbox_dir: Path, cwd: Path, settings: SettingsManager) -> ToolConfig:
    """Build the default tool configuration."""
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    context = ToolContext(
        cwd=cwd.resolve(),
        policy=ToolPolicy.create(sandbox_dir=sandbox_dir.resolve()),
        coordinator=ToolExecutionCoordinator(),
        executor=create_command_executor(settings),
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
        llm: LLM,
        sandbox_dir: Path,
    ) -> Agent:
        """Create the Koda agent for the current settings and session state."""
        tools = self.tools or build_tools(sandbox_dir=sandbox_dir, cwd=self.cwd, settings=settings)
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
