"""The agent runner: the agent for the current session, and the turns it runs."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from structlog import get_logger

from koda import harness
from koda.agent import Agent
from koda.llm import LLMError
from koda.sessions import SaveSessionHook
from koda.tools import ToolError
from koda_tui.state import TurnError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from koda.agent import AgentEvent
    from koda.llm import LLM, Catalog, Model
    from koda.sessions import SessionStore
    from koda_tui.state import AppState

    type Connect = Callable[[Model], Awaitable[LLM]]

logger = get_logger(__name__)


class AgentRunner:
    """Runs turns with the agent for ``state.session`` and ``state.settings.agent_settings``: built
    on first use, and again after ``reset`` or when the session changes."""

    def __init__(
        self,
        state: AppState,
        *,
        catalog: Catalog,
        store: SessionStore,
        connect: Connect,
    ) -> None:
        self._state = state
        self._catalog = catalog
        self._store = store
        self._connect = connect
        self._agent: Agent | None = None
        # OAuth refresh tokens rotate, so concurrent first messages must build it once.
        self._lock = asyncio.Lock()

    def reset(self) -> None:
        """Build a new agent for the next turn, as when the settings change."""
        self._agent = None

    async def respond(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send ``text`` in the current session and stream the agent's response. This is
        the turn's boundary: a failure ends the stream and is shown where the turn failed,
        and one Koda didn't expect is logged."""
        try:
            agent = await self._current()
            async for event in agent.run(text):
                yield event
        except Exception as error:
            self._state.errors.append(TurnError(at=len(self._state.session.messages), error=error))
            if not isinstance(error, LLMError | ToolError):
                logger.exception("turn_failed_unexpectedly")

    async def _current(self) -> Agent:
        async with self._lock:
            if self._agent is None or self._agent.session is not self._state.session:
                self._agent = await self._build()
                self._state.turn = self._agent.turn  # The chat follows this agent's turns.
        return self._agent

    async def _build(self) -> Agent:
        settings = self._state.settings.agent_settings
        model = self._catalog.resolve(settings.provider, settings.model)
        workspace = self._state.workspace
        return Agent(
            await self._connect(model),
            instructions=harness.instructions(workspace),
            tools=harness.tools(workspace),
            hooks=[SaveSessionHook(self._store)],
            session=self._state.session,
            options=settings.request_options(model),
        )
