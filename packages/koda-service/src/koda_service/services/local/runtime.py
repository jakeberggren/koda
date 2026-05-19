from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agent import Agent, AgentConfig
from koda.execution import create_command_executor
from koda.llm import exceptions as llm_exceptions
from koda.llm.catalog import ModelCatalog
from koda.llm.factory import LLMFactory
from koda.tools import ToolConfig

if TYPE_CHECKING:
    from koda.llm import LLM
    from koda.sessions import SessionManager
    from koda_common.settings import SettingsManager
    from koda_service.services.local.config import LocalRuntimeConfig


class LocalRuntime:
    """Owns local agent dependencies and the cached Agent instance."""

    def __init__(
        self,
        *,
        settings: SettingsManager,
        config: LocalRuntimeConfig,
        session_manager: SessionManager,
    ) -> None:
        self.settings = settings
        self.config = config
        self.session_manager = session_manager
        catalog, warnings = ModelCatalog.load()
        self.warnings = warnings
        self.llm_factory = LLMFactory(catalog)
        self.agent: Agent | None = None

    def update_settings(self, settings: SettingsManager) -> None:
        """Replace settings and invalidate runtime objects derived from them."""
        self.settings = settings
        self.invalidate()

    def invalidate(self) -> None:
        """Clear the cached Agent so it is rebuilt on the next request."""
        self.agent = None

    def create_llm(self) -> LLM:
        """Create the selected LLM, or return an injected test/runtime LLM."""
        if self.config.llm is not None:
            return self.config.llm
        if self.settings.provider is None:
            raise llm_exceptions.ProviderSelectionMissingError
        return self.llm_factory.create(self.settings)

    def create_tools(self) -> ToolConfig:
        """Create the configured tool bundle for local command execution."""
        if self.config.tools is not None:
            return self.config.tools
        return ToolConfig.builtins(
            cwd=self.config.cwd,
            sandbox_dir=self.config.sandbox_dir,
            executor=create_command_executor(self.settings),
        )

    def create_agent(self, llm: LLM) -> Agent:
        """Create an Agent wired to the current settings and session manager."""
        agent_config = AgentConfig.from_settings(
            self.settings,
            system_prompt=self.config.system_prompt,
            prompt_context=self.config.prompt_context,
            max_tool_iterations=self.config.max_tool_iterations,
        )
        return Agent(
            llm=llm,
            config=agent_config,
            session_manager=self.session_manager,
            tools=self.create_tools(),
        )

    def get_agent(self) -> Agent:
        """Return the cached Agent, creating it on first use."""
        if self.agent is None:
            self.agent = self.create_agent(self.create_llm())
        return self.agent
