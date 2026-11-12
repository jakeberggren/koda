"""Runtime: the agent, its model and its session, built from the settings."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING

from koda import llm
from koda.agent import Agent, AgentConfig
from koda.context import ContextManager
from koda.execution import HostCommandExecutor, SeatbeltCommandExecutor
from koda.llm import LLMRequestOptions
from koda.llm import exceptions as llm_exceptions
from koda.prompts import SystemPromptLoader
from koda.sessions import Session, SessionNotFoundError
from koda.tools import ToolConfig
from koda_common.settings import SecretsLoadError
from koda_tui import strings
from koda_tui.startup import StartupError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
    from pathlib import Path
    from uuid import UUID

    from koda.agent import AgentEvent
    from koda.execution import CommandExecutor
    from koda.llm import LLM, Catalog, Credentials, Model, Provider
    from koda.sessions import SessionStore
    from koda_common.settings import SettingsManager

    type Connect = Callable[[Model, Credentials], Awaitable[LLM]]


class Runtime:
    """Runs the agent for the current session, with the model the settings select.

    The agent is built on first use and rebuilt after the settings or the session change.
    """

    def __init__(  # noqa: PLR0913 - each dependency is injected as its own keyword argument
        self,
        settings: SettingsManager,
        workspace: Path,
        *,
        catalog: Catalog,
        store: SessionStore,
        warnings: Sequence[str] = (),
        connect: Connect = llm.connect,
    ) -> None:
        self.settings = settings
        self.workspace = workspace
        self.catalog = catalog
        self.store = store
        self.warnings = list(warnings)
        self.session = Session()
        self._connect = connect
        self._agent: Agent | None = None
        # OAuth refresh tokens rotate, so concurrent first runs must build the agent once.
        self._lock = asyncio.Lock()

    async def run(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send ``text`` in the current session and stream the agent's response."""
        agent = await self._get_agent()
        async for event in agent.run(text):
            yield event

    def settings_changed(self) -> None:
        """Rebuild the agent on its next run, with the new settings."""
        self._agent = None

    def new_session(self) -> Session:
        """Start a new session. It is saved once it has a message."""
        self.session = Session()
        self._agent = None
        return self.session

    def open_session(self, session_id: UUID) -> Session:
        """Continue a saved session. Raises ``SessionNotFoundError``."""
        if session_id != self.session.session_id:
            self.session = self.store.get_session(session_id)
            self._agent = None
        return self.session

    def delete_session(self, session_id: UUID) -> None:
        """Delete a session; deleting the current one starts a new one.

        Raises ``SessionNotFoundError`` for an unknown session other than the current one,
        which may not be saved yet.
        """
        if session_id != self.session.session_id:
            self.store.delete_session(session_id)
            return
        with suppress(SessionNotFoundError):
            self.store.delete_session(session_id)
        self.new_session()

    def connected_providers(self) -> list[Provider]:
        """The providers with a connected connection; none if the secrets can't be read."""
        try:
            return [
                provider
                for provider in self.catalog.providers()
                if any(c.is_connected(self.settings) for c in provider.connections)
            ]
        except SecretsLoadError:
            return []

    def connected_models(self) -> list[Model]:
        """The models with a connected connection; none if the secrets can't be read."""
        try:
            return [model for model in self.catalog.models() if model.is_connected(self.settings)]
        except SecretsLoadError:
            return []

    def selected_model(self) -> Model | None:
        """The model the settings select, if it is in the catalog."""
        provider, model_id = self.settings.provider, self.settings.model
        if provider is None or model_id is None:
            return None
        try:
            return self.catalog.model(provider, model_id)
        except llm_exceptions.LLMConfigurationError:
            return None

    def issue(self) -> str | None:
        """What stops the agent from running, or None when it can run."""
        try:
            if not any(model.is_connected(self.settings) for model in self.catalog.models()):
                return strings.Screen.Status.SETUP_REQUIRED
            if self.settings.provider is None or self.settings.model is None:
                return strings.Screen.Status.SELECTION_REQUIRED
            model = self.selected_model()
            if model is None or not model.is_connected(self.settings):
                return strings.Screen.Status.MODEL_UNAVAILABLE
        except SecretsLoadError as error:
            return StartupError.from_secrets_load_error(error).summary
        return None

    async def _get_agent(self) -> Agent:
        if self._agent is None:
            async with self._lock:
                if self._agent is None:
                    self._agent = await self._build_agent()
        return self._agent

    async def _build_agent(self) -> Agent:
        provider, model_id = self.settings.provider, self.settings.model
        if provider is None or model_id is None:
            raise llm_exceptions.ModelSelectionMissingError
        model = self.catalog.model(provider, model_id)
        return Agent(
            llm=await self._connect(model, self.settings),
            config=AgentConfig(
                system_prompt=SystemPromptLoader.for_workspace(self.workspace).load(),
                request_options=LLMRequestOptions(
                    thinking=model.resolve_thinking_option(self.settings.thinking).id,
                    web_search=self.settings.allow_web_search,
                    extended_prompt_retention=self.settings.allow_extended_prompt_retention,
                ),
            ),
            session=self.session,
            store=self.store,
            tools=ToolConfig.builtins(
                cwd=self.workspace,
                sandbox_dir=self.workspace,
                executor=self._executor(),
            ),
            context_manager=ContextManager.from_workspace(self.workspace),
        )

    def _executor(self) -> CommandExecutor:
        if self.settings.bash_execution_sandbox == "seatbelt":
            return SeatbeltCommandExecutor()
        return HostCommandExecutor()
