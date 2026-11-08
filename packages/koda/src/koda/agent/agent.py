from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from koda.agent.runner import AgentRunner
from koda.llm import LLMRequestOptions
from koda.prompts import SystemPrompt
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.agent.events import AgentEvent
    from koda.context.manager import ContextManager
    from koda.llm import LLM
    from koda.sessions import Session, SessionStore
    from koda.tools import ToolConfig

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Static agent configuration."""

    system_prompt: SystemPrompt = field(default_factory=SystemPrompt)
    request_options: LLMRequestOptions = field(default_factory=LLMRequestOptions)


class Agent:
    """Public facade for running a Koda agent."""

    def __init__(  # noqa: PLR0913 - each dependency is injected as its own keyword argument
        self,
        llm: LLM,
        config: AgentConfig,
        *,
        session: Session,
        store: SessionStore | None = None,
        tools: ToolConfig | None = None,
        context_manager: ContextManager | None = None,
    ) -> None:
        self.llm = llm
        self.config = (
            replace(config, system_prompt=context_manager.build_system_prompt(config.system_prompt))
            if context_manager is not None
            else config
        )
        self.session = session
        self.store = store
        self.tools = tools
        self.runner = AgentRunner(
            llm=self.llm,
            config=self.config,
            session=session,
            store=store,
            tools=tools,
        )

        logger.info("agent_initialized", llm=type(llm).__name__)

    async def run(self, user_text: str) -> AsyncIterator[AgentEvent]:
        async for event in self.runner.run(user_text):
            yield event
