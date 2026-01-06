import asyncio
import sys
import traceback
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from koda.agents import Agent
from koda.config import Settings, get_settings
from koda.providers import get_provider_registry
from koda.providers.events import ProviderEvent, TextDelta, ToolCallRequested
from koda.tools import ToolRegistry, filesystem
from koda.utils import exceptions
from koda_tui.backends import Backend, LocalBackend
from koda_tui.input import InputHandler, PromptToolkitInput
from koda_tui.renderer import Renderer, RichRenderer


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
    def __init__(
        self,
        config: AppConfig | None = None,
        input_handler: InputHandler | None = None,
        renderer: Renderer | None = None,
        backend: Backend | None = None,
    ) -> None:
        self.config = config or AppConfig()
        self.settings = get_settings()
        self.input_handler = input_handler or PromptToolkitInput()
        self.renderer = renderer or RichRenderer()
        self.backend = backend or create_backend(self.config, self.settings)

    def _render_event(self, event: ProviderEvent) -> None:
        """Render a single provider event."""
        if isinstance(event, TextDelta):
            self.renderer.write(event.text)
        elif isinstance(event, ToolCallRequested):
            self.renderer.print_tool_call(event.call)

    async def _process_stream(
        self,
        stream_iter: AsyncIterator[ProviderEvent],
        first_chunk: ProviderEvent,
    ) -> None:
        """Process and render the response stream."""
        self._render_event(first_chunk)
        async for chunk in stream_iter:
            self._render_event(chunk)
        self.renderer.flush()

    async def _handle_message(self, user_input: str) -> None:
        """Process a single user message and render the response."""
        try:
            self.renderer.print("")
            with self.renderer.thinking_spinner():
                stream_iter = self.backend.chat(user_input)
                first_chunk = await anext(stream_iter)
            await self._process_stream(stream_iter, first_chunk)
        except exceptions.ProviderRateLimitError as e:
            self.renderer.print_error(f"Rate limit exceeded. {e}")
        except exceptions.ProviderAuthenticationError as e:
            self.renderer.print_error(f"Authentication failed. {e}")
        except exceptions.ProviderAPIError as e:
            self.renderer.print_error(f"API error occurred. {e}")
        except exceptions.ProviderError as e:
            self.renderer.print_error(str(e))
        except exceptions.ToolError as e:
            self.renderer.print_error(str(e))

    async def _chat_loop(self) -> None:
        """Main chat loop."""
        pending_exit = False

        while True:
            try:
                user_input = await self.input_handler.get_input("You: ")
                pending_exit = False

                if not user_input.strip():
                    continue

                await self._handle_message(user_input)

            except (EOFError, KeyboardInterrupt):
                if pending_exit:
                    self.renderer.print("\nGoodbye!")
                    sys.exit(0)
                else:
                    pending_exit = True
                    self.renderer.print("\n[dim]Press Ctrl+C again to exit[/dim]")

    async def run(self) -> None:
        """Start the TUI application."""
        pending_exit = False
        while True:
            try:
                user_input = await self.input_handler.get_input("You: ")
                pending_exit = False
                await self._handle_message(user_input)
            except (EOFError, KeyboardInterrupt, asyncio.CancelledError):
                if pending_exit:
                    self.renderer.print("\nGoodbye!")
                    sys.exit(0)
                else:
                    pending_exit = True
                    self.renderer.print("\n[dim]Press Ctrl+C again to exit[/dim]\n")
            except Exception as e:
                self.renderer.print_error(f"An unexpected error occurred: {e}")
                self.renderer.print_error(traceback.format_exc())
                sys.exit(1)
