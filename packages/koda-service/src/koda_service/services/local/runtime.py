from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from koda.agent import Agent, AgentConfig
from koda.execution import create_command_executor
from koda.llm import exceptions as llm_exceptions
from koda.llm.catalog import ModelCatalog
from koda.llm.factory import LLMFactory
from koda.prompts import SystemPrompt, SystemPromptLoader
from koda.tools import ToolConfig

if TYPE_CHECKING:
    from koda.context.manager import ContextManager
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
        context_manager: ContextManager,
    ) -> None:
        self.settings = settings
        self.config = config
        self.session_manager = session_manager
        self.context_manager = context_manager
        catalog, warnings = ModelCatalog.load()
        self.warnings = warnings
        self.llm_factory = LLMFactory(catalog)
        self.agent: Agent | None = None
        self._agent_lock = asyncio.Lock()

    def update_settings(self, settings: SettingsManager) -> None:
        """Replace settings and invalidate runtime objects derived from them."""
        self.settings = settings
        self.invalidate()

    def invalidate(self) -> None:
        """Clear the cached Agent so it is rebuilt on the next request."""
        self.agent = None

    async def create_llm(self) -> LLM:
        """Create the selected LLM, or return an injected test/runtime LLM."""
        if self.config.llm is not None:
            return self.config.llm
        if self.settings.provider is None:
            raise llm_exceptions.ProviderSelectionMissingError
        return await self.llm_factory.create(self.settings)

    def create_tools(self) -> ToolConfig:
        """Create the configured tool bundle for local command execution."""
        if self.config.tools is not None:
            return self.config.tools
        return ToolConfig.builtins(
            cwd=self.config.cwd,
            sandbox_dir=self.config.sandbox_dir,
            executor=create_command_executor(self.settings),
        )

    def load_system_prompt(self) -> SystemPrompt:
        """Resolve system prompt precedence for this runtime."""
        loaded_prompt = SystemPromptLoader.for_workspace(self.config.cwd).load()
        if loaded_prompt.source is not None:
            return loaded_prompt
        return self.config.system_prompt

    def create_agent(self, llm: LLM) -> Agent:
        """Create an Agent wired to the current settings and session manager."""
        try:
            request_options = self.llm_factory.request_options_for_settings(self.settings)
        except llm_exceptions.LLMConfigurationError:
            if self.config.llm is None:
                raise
            request_options = AgentConfig.from_settings(self.settings).request_options
        agent_config = AgentConfig(
            system_prompt=self.load_system_prompt(),
            request_options=request_options,
        )
        return Agent(
            llm=llm,
            config=agent_config,
            tools=self.create_tools(),
            session_manager=self.session_manager,
            context_manager=self.context_manager,
        )

    async def get_agent(self) -> Agent:
        """Return the cached Agent, creating it on first use."""
        if self.agent is None:
            # OAuth refresh tokens may rotate, so concurrent initialization must refresh only once.
            async with self._agent_lock:
                if self.agent is None:
                    self.agent = self.create_agent(await self.create_llm())
        return self.agent
