"""Main TUI application for Koda."""

from __future__ import annotations

import asyncio
import contextlib
import shutil
from pathlib import Path
from typing import Any

from prompt_toolkit import Application
from prompt_toolkit.layout import Float

from koda.agents import Agent
from koda.providers import get_provider_registry
from koda.providers.events import TextDelta, ToolCallRequested
from koda.tools import ToolConfig, ToolContext, ToolRegistry, get_builtin_tools
from koda_common import SettingsManager
from koda_tui.app.keybindings import create_keybindings
from koda_tui.app.state import AppState
from koda_tui.clients import Client, LocalClient, MockClient
from koda_tui.components.command_palette import Command, CommandPalette
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

        # Command palette
        self._palette: CommandPalette | None = None
        self._palette_float: Float | None = None

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
        if self.state.palette_open:
            self.close_palette()
        else:
            self.open_palette()

    def open_palette(self) -> None:
        """Show the command palette."""
        if not self._app:
            return

        # Calculate palette width: 50% of terminal, min 40, max 80
        term_width = shutil.get_terminal_size().columns
        term_height = shutil.get_terminal_size().lines
        palette_width = max(40, min(80, term_width // 2))
        palette_height = max(5, min(20, term_height // 2))

        self.state.palette_open = True
        self._palette = CommandPalette(
            commands=self._get_palette_commands(),
            on_close=self.close_palette,
            height=palette_height,
        )

        self._palette_float = Float(
            content=self._palette,
            width=palette_width,
        )
        self.layout.root_container.floats.append(self._palette_float)
        self._app.layout.focus(self._palette.search_buffer)
        self.invalidate()

    def close_palette(self) -> None:
        """Hide the command palette."""
        if not self._app:
            return

        self.state.palette_open = False
        if self._palette_float and self._palette_float in self.layout.root_container.floats:
            self.layout.root_container.floats.remove(self._palette_float)
        self._palette = None
        self._palette_float = None
        self._app.layout.focus(self.layout.input_area.buffer)
        self.invalidate()

    def _get_palette_commands(self) -> list[Command]:
        """Get the list of commands for the palette."""
        return [
            Command("Change Model", self._cmd_change_model, "Select a different model"),
            Command("Change Provider", self._cmd_change_provider, "Switch LLM provider"),
            Command("New Session", self._cmd_new_session, "Clear chat and start fresh"),
            Command("List Sessions", self._cmd_list_sessions, "View previous sessions"),
        ]

    def _cmd_change_model(self) -> None:
        """Handle change model command. Not yet implemented."""

    def _cmd_change_provider(self) -> None:
        """Handle change provider command. Not yet implemented."""

    def _cmd_new_session(self) -> None:
        """Handle new session command."""

    def _cmd_list_sessions(self) -> None:
        """Handle list sessions command. Not yet implemented."""

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = self._create_application()
        await self._app.run_async()
