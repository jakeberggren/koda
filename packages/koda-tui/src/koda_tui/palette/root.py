"""Root menu: the commands the palette opens with."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from koda.llm.auth.registry import ProviderAuthRegistry
from koda_tui.palette.menus.input import InputMenu
from koda_tui.palette.menus.models import ModelMenu
from koda_tui.palette.menus.providers import ProviderMenu
from koda_tui.palette.menus.sessions import SessionMenu
from koda_tui.palette.menus.theme import ThemeMenu
from koda_tui.palette.menus.thinking import ThinkingMenu
from koda_tui.ui.widgets import ListItem, Picker

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_tui.palette.context import PaletteContext
    from koda_tui.state import AppState

TITLE = "Commands"


class Group(StrEnum):
    """The headings commands are listed under, in the order they first appear."""

    AGENT = "Agent"
    SESSIONS = "Sessions"
    APPEARANCE = "Appearance"
    SYSTEM = "System"


@dataclass(frozen=True, slots=True, kw_only=True)
class Command:
    """A command: how it is listed, what running it does, and when it is offered."""

    label: str
    detail: str
    group: Group
    run: Callable[[], None]
    available: Callable[[AppState], bool] = lambda _state: True


class RootMenu:
    """The commands, grouped. Each opens a menu or acts directly."""

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._settings = context.settings
        self._state = context.state
        sessions = SessionMenu(context)
        self._commands = [
            Command(
                label="Connect Provider",
                detail="Configure LLM provider API keys",
                group=Group.AGENT,
                run=ProviderMenu(context, ProviderAuthRegistry.default()).open,
            ),
            Command(
                label="Set Thinking Level",
                detail="Select model reasoning effort",
                group=Group.AGENT,
                run=ThinkingMenu(context).open,
                available=lambda state: _ready(state) and state.thinking_supported,
            ),
            Command(
                label="Switch Model",
                detail="Select a different model",
                group=Group.AGENT,
                run=ModelMenu(context).open,
                available=lambda state: bool(state.configured_providers),
            ),
            Command(
                label="New Session",
                detail="Start a new conversation",
                group=Group.SESSIONS,
                run=sessions.new,
                available=_ready,
            ),
            Command(
                label="List Sessions",
                detail="Switch between sessions",
                group=Group.SESSIONS,
                run=sessions.open,
                available=_ready,
            ),
            Command(
                label="Select Theme",
                detail="Choose auto, light, or dark mode",
                group=Group.APPEARANCE,
                run=ThemeMenu(context).open,
            ),
            Command(
                label="Toggle Scrollbar",
                detail="Show or hide the chat scrollbar",
                group=Group.APPEARANCE,
                run=self._toggle_scrollbar,
            ),
            Command(
                label="Input Mode",
                detail="Prefer queue or steer as default input mode",
                group=Group.SYSTEM,
                run=InputMenu(context).open,
            ),
        ]

    def open(self) -> None:
        self._overlays.open(
            Picker(
                TITLE,
                self.items(),
                on_select=lambda item: item.data.run(),
                on_close=self._overlays.close,
            ),
        )

    def items(self) -> list[ListItem[Command]]:
        """The commands offered right now."""
        return [
            ListItem(label=command.label, detail=command.detail, group=command.group, data=command)
            for command in self._commands
            if command.available(self._state)
        ]

    def _toggle_scrollbar(self) -> None:
        self._settings.tui.set("show_scrollbar", not self._settings.tui.show_scrollbar)
        self._overlays.close_all()


def _ready(state: AppState) -> bool:
    return state.service_status.is_ready
