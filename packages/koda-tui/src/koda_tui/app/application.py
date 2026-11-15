from __future__ import annotations

import asyncio
from copy import replace
from typing import TYPE_CHECKING, Any

from prompt_toolkit.filters import Condition

from koda.llm import (
    CredentialsError,
    ModelNotConnected,
    ModelNotFound,
    ModelUnavailable,
    NoModelSelected,
    NoProviderConnected,
)
from koda_tui import strings
from koda_tui.app.agent import AgentRunner
from koda_tui.app.exit import ExitPrompt
from koda_tui.app.fullscreen import FullScreenApplication
from koda_tui.app.keybindings import create_keybindings
from koda_tui.appearance import Appearance
from koda_tui.outbox import Outbox
from koda_tui.palette.context import PaletteContext
from koda_tui.palette.palette import CommandPalette
from koda_tui.state import AppState
from koda_tui.terminal import Terminal
from koda_tui.views import Screen

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from pathlib import Path

    from koda.agent import AgentEvent
    from koda.llm import Catalog, Credentials
    from koda.sessions import SessionStore
    from koda_tui.app.agent import Connect
    from koda_tui.appearance import RGBColor
    from koda_tui.settings import Settings


ISSUES: dict[type[ModelUnavailable], str] = {
    NoProviderConnected: strings.Screen.Status.SETUP_REQUIRED,
    NoModelSelected: strings.Screen.Status.SELECTION_REQUIRED,
    ModelNotFound: strings.Screen.Status.MODEL_NOT_FOUND,
    ModelNotConnected: strings.Screen.Status.MODEL_NOT_CONNECTED,
}


class KodaTuiApp:
    """Main TUI application: wires the parts together and holds the app-wide commands."""

    def __init__(  # noqa: PLR0913 - the parts main builds, each its own keyword argument
        self,
        settings: Settings,
        workspace: Path,
        *,
        catalog: Catalog,
        credentials: Credentials,
        store: SessionStore,
        connect: Connect,
        warnings: Sequence[str] = (),
    ) -> None:
        self._catalog = catalog
        self._store = store
        self._app: FullScreenApplication | None = None  # Created on run.
        self._terminal = Terminal(on_background=self.on_terminal_background)

        self.state = AppState(workspace=workspace, settings=settings, warnings=list(warnings))
        self._agent = AgentRunner(self.state, catalog=catalog, store=store, connect=connect)
        self._refresh()
        self.exit_prompt = ExitPrompt(self.state, invalidate=self.invalidate)
        self.appearance = Appearance(settings.tui_settings.theme)
        self.screen = Screen(
            self.state,
            on_submit=self.submit,
            show_scrollbar=Condition(lambda: self.state.settings.tui_settings.show_scrollbar),
        )
        self.outbox = Outbox(state=self.state, respond=self.respond, invalidate=self.invalidate)
        self._palette = CommandPalette(
            PaletteContext(
                overlays=self.screen.overlays,
                catalog=catalog,
                credentials=credentials,
                store=store,
                update_settings=self.update_settings,
                state=self.state,
                outbox=self.outbox,
                terminal=self._terminal,
            ),
        )

    async def run(self) -> None:
        """Start the TUI application."""
        self._app = FullScreenApplication(
            self.screen,
            key_bindings=create_keybindings(self),
            style=self.appearance.style,
            terminal=self._terminal,
        )
        asyncio.get_running_loop().set_exception_handler(self._stop)
        try:
            await self._app.run_async(set_exception_handler=False)
        finally:
            self._terminal.close()  # In case the final render failed before turning it off.

    def _stop(self, loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        """A bug outside a turn, such as in a key binding, a redraw or a task, stops Koda
        with it, for ``main`` to report; anything else goes to asyncio's own handler."""
        error = context.get("exception")
        if isinstance(error, Exception) and self._app and not self._app.is_done:
            self._app.exit(exception=error)
        else:
            loop.default_exception_handler(context)

    def invalidate(self) -> None:
        """Trigger a UI refresh."""
        if self._app:
            self._app.invalidate()

    def exit(self) -> None:
        """Exit the application."""
        if self._app:
            self._app.exit()

    def cycle_thinking(self) -> None:
        """Move to the active model's next thinking level, wrapping around, once Koda is
        ready."""
        model, settings = self.state.active_model, self.state.settings
        if self.state.issue is not None or model is None:
            return
        if (thinking := model.thinking.next(settings.agent_settings.thinking)) is not None:
            agent_settings = replace(settings.agent_settings, thinking=thinking)
            self.update_settings(replace(settings, agent_settings=agent_settings))

    def toggle_palette(self) -> None:
        """Open the command palette, or close it and any dialogs it opened."""
        if self.screen.overlays.is_open:
            self.screen.overlays.close_all()
        else:
            self._palette.open()

    def submit(self, text: str, *, alternate: bool) -> bool:
        """While Koda responds, Enter queues and Alt+Enter steers, or the other way
        round when the input mode prefers steering. Writing a message takes back a
        press of Ctrl+C. Whether the message was taken."""
        self.exit_prompt.dismiss()
        return self.outbox.submit(
            text,
            steer=alternate == self.state.settings.tui_settings.queue_inputs,
        )

    def respond(self, text: str) -> AsyncIterator[AgentEvent]:
        """Send ``text`` in the current session and stream the agent's response."""
        return self._agent.respond(text)

    def update_settings(self, settings: Settings) -> None:
        """Save ``settings`` and apply them; the next turn's agent is made with them. Also
        what to call after a credential changes, to show what it connects."""
        settings.save()
        self.state.settings = settings
        self._refresh()
        self.appearance.theme = settings.tui_settings.theme
        self.invalidate()

    def _refresh(self) -> None:
        """Take the providers connected now and the model the settings pick, or say what
        stops Koda from responding."""
        state, agent = self.state, self.state.settings.agent_settings
        try:
            state.connected_providers = self._catalog.connected.providers
            state.active_model = self._catalog.resolve(agent.provider, agent.model)
            state.issue = None
        except ModelUnavailable as unavailable:
            state.active_model, state.issue = None, ISSUES[type(unavailable)]
        except CredentialsError:
            state.connected_providers, state.active_model = [], None
            state.issue = strings.Screen.Status.CREDENTIALS_UNREADABLE

    def on_terminal_background(self, background: RGBColor) -> None:
        self.appearance.terminal_background = background
        self.invalidate()
