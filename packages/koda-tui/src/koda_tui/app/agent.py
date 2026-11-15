"""The agent runner: the turns of the current session, each with an agent of its own."""

from __future__ import annotations

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
    from koda.llm import LLM, Catalog, LLMOptions, Model
    from koda.sessions import SessionStore
    from koda_tui.state import AppState

    type Connect = Callable[[Model, LLMOptions], Awaitable[LLM]]

logger = get_logger(__name__)


class AgentRunner:
    """Runs turns with an agent for ``state.session`` and ``state.settings.agent_settings``,
    made anew for each turn."""

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
        self._llm: LLM | None = None
        self._llm_for: tuple[Model, LLMOptions] | None = None  # What it was connected for.

    async def respond(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send ``text`` in the current session and stream the agent's response. This is
        the turn's boundary: a failure ends the stream and is shown where the turn failed,
        and one Koda didn't expect is logged."""
        try:
            agent = await self._agent()
            self._state.turn = agent.turn  # The chat follows this turn.
            async for event in agent.run(text):
                yield event
        except Exception as error:
            self._state.errors.append(TurnError(at=len(self._state.session.messages), error=error))
            if not isinstance(error, LLMError | ToolError):
                logger.exception("turn_failed_unexpectedly")

    async def _agent(self) -> Agent:
        """An agent for this turn, with the settings, session and workspace as they are now.
        The LLM is kept while the model and options stay the same, so its connections are
        reused."""
        settings = self._state.settings.agent_settings
        model = self._catalog.resolve(settings.provider, settings.model)
        options = settings.request_options(model)
        llm = self._llm
        if llm is None or self._llm_for != (model, options):
            llm = await self._connect(model, options)
            self._llm, self._llm_for = llm, (model, options)
        workspace = harness.Workspace(self._state.workspace)
        return Agent(
            llm,
            instructions=harness.instructions(workspace),
            tools=harness.tools(workspace),
            hooks=[SaveSessionHook(self._store)],
            session=self._state.session,
        )
