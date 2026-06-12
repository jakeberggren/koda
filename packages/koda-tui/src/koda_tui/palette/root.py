"""Root palette menu item construction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from koda_tui.state import AppState


class RootMenu:
    """Root palette menu."""

    def __init__(self, state: AppState) -> None:
        self._state = state

    def _agent_items(self) -> list[ListItem]:
        items: list[ListItem] = []
        if self._state.thinking_supported:
            items.append(
                ListItem(
                    id="set_thinking",
                    label="Set Thinking Level",
                    detail="Select model reasoning effort",
                    group="Agent",
                )
            )
        return items

    @staticmethod
    def _session_items() -> list[ListItem]:
        return [
            ListItem(
                id="new_session",
                label="New Session",
                detail="Start a new conversation",
                group="Sessions",
            ),
            ListItem(
                id="list_sessions",
                label="List Sessions",
                detail="Switch between sessions",
                group="Sessions",
            ),
        ]

    def items(self) -> list[ListItem]:
        """Build the top-level palette items."""
        items = [
            ListItem(
                id="connect_provider",
                label="Connect Provider",
                detail="Configure LLM provider API keys",
                group="Agent",
            ),
            ListItem(
                id="select_theme",
                label="Select Theme",
                detail="Choose auto, light, or dark mode",
                group="Appearance",
            ),
            ListItem(
                id="toggle_scrollbar",
                label="Toggle Scrollbar",
                detail="Show or hide the chat scrollbar",
                group="Appearance",
            ),
            ListItem(
                id="toggle_queue_inputs",
                label="Toggle Queue Inputs",
                detail="Queue or cancel on input during streaming",
                group="System",
            ),
        ]

        if self._state.configured_providers:
            items.insert(
                1,
                ListItem(
                    id="switch_model",
                    label="Switch Model",
                    detail="Select a different model",
                    group="Agent",
                ),
            )

        if self._state.service_status.is_ready:
            items[1:1] = [*self._agent_items(), *self._session_items()]

        return items
