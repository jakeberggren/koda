from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from koda.agent import Agent, AgentConfig
from koda.execution import HostCommandExecutor, SeatbeltCommandExecutor
from koda.llm import Catalog, LLMRequestOptions, connect
from koda.llm import exceptions as llm_exceptions
from koda.prompts import SystemPrompt, SystemPromptLoader
from koda.tools import ToolConfig

if TYPE_CHECKING:
    from koda.context.manager import ContextManager
    from koda.execution import CommandExecutor
    from koda.llm import LLM
    from koda.sessions import Session, SessionStore
    from koda_common.settings import SettingsManager
    from koda_service.services.local.config import LocalRuntimeConfig


class LocalRuntime:
    """Owns local agent dependencies and the cached Agent instance."""

    def __init__(
        self,
        *,
        settings: SettingsManager,
        config: LocalRuntimeConfig,
        session_store: SessionStore,
        context_manager: ContextManager,
    ) -> None:
        self.settings = settings
        self.config = config
        self.session_store = session_store
        self.context_manager = context_manager
        self.catalog, self.warnings = Catalog.load()
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
        if self.settings.model is None:
            raise llm_exceptions.ModelSelectionMissingError
        model = self.catalog.model(self.settings.provider, self.settings.model)
        return await connect(model, self.settings, tracing=self.config.tracing)

    def create_executor(self) -> CommandExecutor:
        """Create the command executor selected in settings."""
        if self.settings.bash_execution_sandbox == "seatbelt":
            return SeatbeltCommandExecutor()
        return HostCommandExecutor()

    def create_tools(self) -> ToolConfig:
        """Create the configured tool bundle for local command execution."""
        if self.config.tools is not None:
            return self.config.tools
        return ToolConfig.builtins(
            cwd=self.config.cwd,
            sandbox_dir=self.config.sandbox_dir,
            executor=self.create_executor(),
        )

    def load_system_prompt(self) -> SystemPrompt:
        """Resolve system prompt precedence for this runtime."""
        loaded_prompt = SystemPromptLoader.for_workspace(self.config.cwd).load()
        if loaded_prompt.source is not None:
            return loaded_prompt
        return self.config.system_prompt

    def create_agent(self, llm: LLM, session: Session) -> Agent:
        """Create an Agent for ``session``, wired to the current settings."""
        return Agent(
            llm=llm,
            config=AgentConfig(
                system_prompt=self.load_system_prompt(),
                request_options=LLMRequestOptions(
                    thinking=self.resolve_thinking(),
                    web_search=self.settings.allow_web_search,
                    extended_prompt_retention=self.settings.allow_extended_prompt_retention,
                ),
            ),
            session=session,
            store=self.session_store,
            tools=self.create_tools(),
            context_manager=self.context_manager,
        )

    def resolve_thinking(self) -> str:
        """The selected thinking mode, resolved against what the model supports."""
        provider, model = self.settings.provider, self.settings.model
        if provider is None or model is None:
            if self.config.llm is None:
                raise llm_exceptions.ProviderSelectionMissingError
            return self.settings.thinking
        try:
            return (
                self.catalog.model(provider, model)
                .resolve_thinking_option(self.settings.thinking)
                .id
            )
        except llm_exceptions.LLMConfigurationError:
            if self.config.llm is None:
                raise
            return self.settings.thinking

    async def get_agent(self, session: Session) -> Agent:
        """Return the cached Agent, creating it for ``session`` on first use."""
        if self.agent is None:
            # OAuth refresh tokens may rotate, so concurrent initialization must refresh only once.
            async with self._agent_lock:
                if self.agent is None:
                    self.agent = self.create_agent(await self.create_llm(), session)
        return self.agent
