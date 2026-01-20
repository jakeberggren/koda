"""Main TUI application for Koda."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
from pathlib import Path
from typing import Any

from prompt_toolkit import Application

from koda.agents import Agent
from koda.providers import get_provider_registry
from koda.providers.events import TextDelta, ToolCallRequested
from koda.providers.exceptions import ProviderAuthenticationError
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda_common import SettingsManager
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.state import AppState
from koda_tui.clients import Client, LocalClient, MockClient
from koda_tui.components.palette import Command, CommandPalette, PaletteManager, get_main_commands
from koda_tui.layout import TUILayout
from koda_tui.rendering import TUI_STYLE


def _create_tool_config(sandbox_dir: Path) -> ToolConfig:
    """Create and configure tools with registry and context."""
    registry = ToolRegistry()
    registry.register_all(get_builtin_tools())
    context = ToolContext.default(sandbox_dir=sandbox_dir)
    return ToolConfig(registry=registry, context=context)


def _create_client(settings: SettingsManager, sandbox_dir: Path) -> Client:
    """Create and configure the client with agent."""
    if settings.use_mock_client:
        return MockClient()
    provider = get_provider_registry().create(settings.provider, settings, model=settings.model)
    agent = Agent(provider=provider, tools=_create_tool_config(sandbox_dir))
    return LocalClient(agent)


class KodaTuiApp:
    """Main TUI application."""

    def __init__(
        self,
        sandbox_dir: Path | None = None,
        client: Client | None = None,
    ) -> None:
        self._sandbox_dir = sandbox_dir or Path.cwd().resolve()
        self._settings = SettingsManager.get_instance()
        self._client = client or _create_client(self._settings, self._sandbox_dir)

        # Subscribe to settings changes
        self._unsubscribe = self._settings.subscribe(self._on_settings_changed)

        # Initialize state
        self.state = AppState(
            provider_name=self._settings.provider,
            model_name=self._settings.model,
        )

        # Initialize layout
        self.layout = TUILayout(self.state)

        # Application instance (created on run)
        self._app: Application | None = None
        self._streaming_task: asyncio.Task | None = None
        self._spinner_task: asyncio.Task | None = None

        # Palette manager for command palettes and dialogs
        self._palette_manager = PaletteManager(self.layout)

    def _on_settings_changed(self, name: str, _old: Any, _new: Any) -> None:
        """Handle settings changes."""
        if name in ("provider", "model") or name.startswith("api_keys."):
            self.state.provider_name = self._settings.provider
            self.state.model_name = self._settings.model
            self._client = _create_client(self._settings, self._sandbox_dir)
            self.invalidate()

    def _create_application(self) -> Application:
        """Create the prompt_toolkit Application."""
        app = Application(
            layout=self.layout.create_layout(),
            key_bindings=create_keybindings(self),
            style=TUI_STYLE,
            full_screen=True,
            mouse_support=True,
        )
        app.ttimeoutlen = 0.01  # Reduce escape key delay (default 0.5s)
        return app

    async def _run_spinner(self) -> None:
        """Periodically refresh UI to animate the spinner."""
        while True:
            await asyncio.sleep(0.1)
            self.invalidate()

    def _start_spinner(self) -> None:
        """Start the spinner animation task."""
        if self._spinner_task is None:
            self._spinner_task = asyncio.create_task(self._run_spinner())

    async def _stop_spinner(self) -> None:
        """Stop the spinner animation task."""
        if self._spinner_task:
            self._spinner_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._spinner_task
            self._spinner_task = None

    async def _process_stream(self, message: str) -> None:
        """Process the response stream from backend."""
        stream = self._client.chat(message)

        async for event in stream:
            if isinstance(event, TextDelta):
                await self._stop_spinner()  # Stop spinner once content arrives
                self.state.append_delta(event.text)
                self.invalidate()
            elif isinstance(event, ToolCallRequested):
                self.state.transition_to_tool(event.call)
                self.invalidate()

    def invalidate(self) -> None:
        """Trigger a UI refresh."""
        if self._app:
            self._app.invalidate()

    async def send_message(self, text: str) -> None:
        """Send a message and process the response stream."""
        self.state.begin_response(text)
        self._start_spinner()
        self.invalidate()

        try:
            self._streaming_task = asyncio.create_task(self._process_stream(text))
            await self._streaming_task
        except asyncio.CancelledError:
            pass
        except ProviderAuthenticationError:
            provider = self._settings.provider
            error_msg = (
                f"\n\n**Authentication failed for {provider.title()}.**\n\n"
                f"Please check your API key. Press `Ctrl+P` → `Connect Provider` to update it."
            )
            self.state.append_delta(error_msg)
        except Exception as e:
            error_msg = f"\n\n**Error:** {type(e).__name__}: {e}"
            self.state.append_delta(error_msg)
        finally:
            await self._stop_spinner()
            self.state.end_response()
            self._streaming_task = None
            self.invalidate()

    def cancel_streaming(self) -> None:
        """Cancel the current streaming operation."""
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    # Command palette methods

    def toggle_palette(self) -> None:
        """Toggle command palette visibility."""
        if self._palette_manager.is_open:
            self._palette_manager.clear()
            self.state.palette_open = False
        else:
            self.open_palette()
        self.invalidate()

    def open_palette(self, commands: list[Command] | None = None) -> None:
        """Show the command palette with given commands (or default)."""
        if not self._app:
            return

        # Calculate palette dimensions
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        palette_width = max(40, min(80, term_width // 2))
        palette_height = max(5, min(20, term_height // 2))

        if commands is None:
            commands = get_main_commands(
                settings=self._settings,
                palette_manager=self._palette_manager,
                on_close=self._on_palette_close,
                open_palette=self.open_palette,
            )

        palette = CommandPalette(
            commands=commands,
            on_close=self._on_palette_close,
            height=palette_height,
        )

        self._palette_manager.push(palette, width=palette_width)
        self.state.palette_open = True
        self.invalidate()

    def _on_palette_close(self) -> None:
        """Handle palette/dialog close (Escape pressed)."""
        still_open = self._palette_manager.pop()
        self.state.palette_open = still_open
        self.invalidate()

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        self._palette_manager.set_app(self._app)
        await self._app.run_async()
