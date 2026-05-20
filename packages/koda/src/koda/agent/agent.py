from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.agent.errors import AgentConfigError
from koda.agent.prompts import PromptContext, SystemPrompt, render_prompt
from koda.agent.runner import AgentRunner
from koda.llm import LLMRequestOptions
from koda.sessions import InMemorySessionStore, SessionManager
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.agent.events import AgentEvent
    from koda.llm import LLM
    from koda.tools import ToolConfig
    from koda_common.settings import SettingsManager

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Static agent configuration."""

    prompt_context: PromptContext | None = None
    system_prompt: SystemPrompt = field(default_factory=SystemPrompt)
    request_options: LLMRequestOptions = field(default_factory=LLMRequestOptions)
    max_tool_iterations: int = 30

    def __post_init__(self) -> None:
        if self.max_tool_iterations < 1:
            raise AgentConfigError(
                field_name="max_tool_iterations",
                value=self.max_tool_iterations,
                expected="an integer greater than or equal to 1",
            )

        render_prompt(self.system_prompt, self.prompt_context)

    @classmethod
    def from_settings(
        cls,
        settings: SettingsManager,
        *,
        system_prompt: SystemPrompt | None = None,
        prompt_context: PromptContext | None = None,
        max_tool_iterations: int = 30,
    ) -> AgentConfig:
        return cls(
            system_prompt=system_prompt or SystemPrompt(),
            prompt_context=prompt_context,
            request_options=LLMRequestOptions(
                thinking=settings.thinking,
                web_search=settings.allow_web_search,
                extended_prompt_retention=settings.allow_extended_prompt_retention,
            ),
            max_tool_iterations=max_tool_iterations,
        )


class Agent:
    """Public facade for running a Koda agent."""

    def __init__(
        self,
        llm: LLM,
        config: AgentConfig,
        session_manager: SessionManager | None = None,
        tools: ToolConfig | None = None,
    ) -> None:
        self.llm = llm
        self.config = config
        self.session_manager = session_manager or SessionManager(InMemorySessionStore())
        self.tools = tools
        self.instructions = render_prompt(
            self.config.system_prompt,
            self.config.prompt_context,
        )
        self.runner = AgentRunner(
            llm=self.llm,
            config=self.config,
            session_manager=self.session_manager,
            instructions=self.instructions,
            tools=self.tools,
        )

        logger.info("agent_initialized", llm=type(llm).__name__)

    async def run(self, user_text: str) -> AsyncIterator[AgentEvent]:
        async for event in self.runner.run(user_text):
            yield event
