from __future__ import annotations

from typing import TYPE_CHECKING

from koda.agents import Agent
from koda.providers import get_provider_registry
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda_tui.clients import Client

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from koda.providers.events import ProviderEvent
    from koda_common import SettingsManager


class LocalClient(Client):
    """Client that uses koda core directly."""

    def __init__(self, settings: SettingsManager, sandbox_dir: Path) -> None:
        self._settings = settings
        self._sandbox_dir = sandbox_dir
        self._agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Create and configure the agent with provider and tools."""
        provider = get_provider_registry().create(
            self._settings.provider, self._settings, model=self._settings.model
        )
        registry = ToolRegistry()
        registry.register_all(get_builtin_tools())
        context = ToolContext.default(sandbox_dir=self._sandbox_dir)
        tools = ToolConfig(registry=registry, context=context)
        return Agent(provider=provider, tools=tools)

    def chat(self, message: str) -> AsyncIterator[ProviderEvent]:
        """Send a message and stream response events."""
        return self._agent.run(message)

    def list_providers(self) -> list[str]:
        """List available providers."""
        return get_provider_registry().supported()

    def list_models(self, provider: str) -> list[str]:
        """List available models for a provider."""
        raise NotImplementedError
