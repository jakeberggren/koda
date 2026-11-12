from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from koda.agent.runner import AgentRunner
from koda.context import ContextManager
from koda.execution import HostCommandExecutor, SeatbeltCommandExecutor
from koda.prompts import SystemPromptLoader
from koda.tools import ToolConfig
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.agent.events import AgentEvent
    from koda.execution import Sandbox
    from koda.llm import LLM, LLMRequestOptions
    from koda.sessions import Session, SessionStore

logger = get_logger(__name__)


class Agent:
    """A Koda agent working in ``workspace``: the built-in tools, the workspace's
    ``SYSTEM.md`` (or ``~/.koda``'s, or the default prompt), and its ``AGENTS.md``.

    Messages go to ``session``, which is saved to ``store`` after each one if given.
    """

    def __init__(  # noqa: PLR0913 - each option is its own keyword argument
        self,
        llm: LLM,
        *,
        session: Session,
        workspace: Path | None = None,
        store: SessionStore | None = None,
        options: LLMRequestOptions | None = None,
        sandbox: Sandbox = "host",
    ) -> None:
        self.llm = llm
        self.session = session
        self.workspace = (workspace or Path.cwd()).resolve()
        self.store = store
        self.tools = ToolConfig.builtins(
            cwd=self.workspace,
            sandbox_dir=self.workspace,
            executor=SeatbeltCommandExecutor() if sandbox == "seatbelt" else HostCommandExecutor(),
        )
        system_prompt = ContextManager.from_workspace(self.workspace).build_system_prompt(
            SystemPromptLoader.for_workspace(self.workspace).load()
        )
        self.runner = AgentRunner(
            llm=llm,
            session=session,
            store=store,
            tools=self.tools,
            system_prompt=system_prompt,
            options=options,
        )
        logger.info("agent_initialized", llm=type(llm).__name__)

    async def run(self, user_text: str) -> AsyncIterator[AgentEvent]:
        """Send ``user_text`` and stream the response."""
        async for event in self.runner.run(user_text):
            yield event
