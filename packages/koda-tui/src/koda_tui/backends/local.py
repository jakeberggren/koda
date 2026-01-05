from __future__ import annotations

from collections.abc import AsyncIterator

from koda.agents import Agent
from koda.providers.events import ProviderEvent
from koda_tui.backends.base import Backend


class LocalBackend(Backend):
    """Backend that uses koda core directly."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def chat(self, message: str) -> AsyncIterator[ProviderEvent]:
        """Send a message and stream response events."""
        return self._agent.run(message)
