"""Main TUI application for Koda."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit import Application

from koda.agents import Agent
from koda.config import Settings, get_settings
from koda.providers import get_provider_registry
from koda.providers.events import TextDelta, ToolCallRequested
from koda.tools import ToolRegistry, filesystem
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.state import AppState
from koda_tui.backends import Backend, LocalBackend
from koda_tui.layout import TUILayout
from koda_tui.rendering import TUI_STYLE


@dataclass
class AppConfig:
    """Configuration for the Koda TUI application."""

    provider: str | None = None
    model: str | None = None
    sandbox_dir: Path = field(default_factory=lambda: Path.cwd().resolve())


def create_app_config(
    provider: str | None = None,
    model: str | None = None,
    sandbox_dir: Path | None = None,
    settings: Settings | None = None,
) -> AppConfig:
    """Create and configure the application configuration."""
    settings = settings or get_settings()
    return AppConfig(
        provider=provider or settings.KODA_DEFAULT_PROVIDER,
        model=model or settings.KODA_DEFAULT_MODEL,
        sandbox_dir=sandbox_dir or Path.cwd().resolve(),
    )


def create_tool_registry(config: AppConfig) -> ToolRegistry:
    """Create and configure the tool registry."""
    registry = ToolRegistry()
    sandbox_dir = config.sandbox_dir
    registry.register(filesystem.ReadFileTool(sandbox_dir=sandbox_dir))
    registry.register(filesystem.WriteFileTool(sandbox_dir=sandbox_dir))
    registry.register(filesystem.ListDirectoryTool(sandbox_dir=sandbox_dir))
    registry.register(filesystem.FileExistsTool(sandbox_dir=sandbox_dir))
    return registry


def create_backend(config: AppConfig, settings: Settings) -> Backend:
    """Create and configure the backend with agent."""
    provider_name = (config.provider or settings.KODA_DEFAULT_PROVIDER).lower()
    provider = get_provider_registry().create(provider_name, settings, model=config.model)

    agent = Agent(
        provider=provider,
        tool_registry=create_tool_registry(config),
    )

    return LocalBackend(agent)


class KodaTuiApp:
    """Main TUI application."""

    def __init__(
        self,
        config: AppConfig | None = None,
        backend: Backend | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.settings = get_settings()
        self.backend = backend or create_backend(self.config, self.settings)

        # Initialize state
        self.state = AppState(
            provider_name=self.config.provider or "unknown",
            model_name=self.config.model or "default",
        )

        # Initialize layout
        self.layout = TUILayout(self.state)

        # Application instance (created on run)
        self._app: Application | None = None
        self._streaming_task: asyncio.Task | None = None
        self._spinner_task: asyncio.Task | None = None

    def _create_application(self) -> Application:
        """Create the prompt_toolkit Application."""
        return Application(
            layout=self.layout.create_layout(),
            key_bindings=create_keybindings(self),
            style=TUI_STYLE,
            full_screen=True,
            mouse_support=True,
        )

    def invalidate(self) -> None:
        """Trigger a UI refresh."""
        if self._app:
            self._app.invalidate()

    async def _run_spinner(self) -> None:
        """Periodically refresh UI to animate the spinner."""
        while True:
            await asyncio.sleep(0.1)
            self.invalidate()

    def _start_spinner(self) -> None:
        """Start the spinner animation task."""
        if self._spinner_task is None:
            self._spinner_task = asyncio.create_task(self._run_spinner())

    def _stop_spinner(self) -> None:
        """Stop the spinner animation task."""
        if self._spinner_task:
            self._spinner_task.cancel()
            self._spinner_task = None

    async def send_message(self, text: str) -> None:
        """Send a message and process the response stream."""
        # Reset exit request when user sends a message
        self.state.reset_exit_request()

        # Add user message to history
        self.state.add_user_message(text)
        self.invalidate()

        # Start streaming response
        self.state.start_streaming()
        self._start_spinner()
        self.invalidate()

        try:
            self._streaming_task = asyncio.create_task(self._process_stream(text))
            await self._streaming_task
        except asyncio.CancelledError:
            # Streaming was cancelled
            pass
        finally:
            self._stop_spinner()
            self.state.finish_streaming()
            self.state.set_active_tool(None)
            self._streaming_task = None
            self.invalidate()

    async def _process_stream(self, message: str) -> None:
        """Process the response stream from backend."""
        stream = self.backend.chat(message)

        async for event in stream:
            if isinstance(event, TextDelta):
                self._stop_spinner()  # Stop spinner once content arrives
                self.state.append_delta(event.text)
                self.invalidate()
            elif isinstance(event, ToolCallRequested):
                # Finalize current streaming content before tool
                if self.state.current_streaming_content:
                    self.state.finish_streaming()
                    self.state.start_streaming()

                self.state.set_active_tool(event.call)
                self.invalidate()

    def cancel_streaming(self) -> None:
        """Cancel the current streaming operation."""
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        await self._app.run_async()
