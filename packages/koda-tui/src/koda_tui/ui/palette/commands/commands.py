from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands import model_commands, provider_commands
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common import SettingsManager
    from koda_tui.clients import Client
    from koda_tui.ui.palette.palette_manager import PaletteManager


def get_commands(  # noqa: C901 - allow complex
    client: Client,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    """Get the root palette commands."""

    def cmd_connect_provider() -> None:
        commands = provider_commands.get_commands(
            client=client,
            settings=settings,
            palette_manager=palette_manager,
        )
        palette_manager.open_palette(commands)

    def cmd_switch_model() -> None:
        commands = model_commands.get_commands(
            client=client,
            settings=settings,
            palette_manager=palette_manager,
        )
        palette_manager.open_palette(commands)

    def cmd_toggle_theme() -> None:
        new_theme = "light" if settings.theme == "dark" else "dark"
        settings.theme = new_theme
        palette_manager.close_all()

    def cmd_toggle_scrollbar() -> None:
        settings.show_scrollbar = not settings.show_scrollbar
        palette_manager.close_all()

    def cmd_toggle_queue_inputs() -> None:
        settings.queue_inputs = not settings.queue_inputs
        palette_manager.close_all()

    return [
        Command(
            "Connect Provider",
            cmd_connect_provider,
            "Configure LLM provider API keys",
            group="Agent",
        ),
        Command(
            "Switch Model",
            cmd_switch_model,
            "Select a different model",
            group="Agent",
        ),
        Command(
            "Toggle Theme",
            cmd_toggle_theme,
            "Switch between dark and light mode",
            group="Appearance",
        ),
        Command(
            "Toggle Scrollbar",
            cmd_toggle_scrollbar,
            "Show or hide the chat scrollbar",
            group="Appearance",
        ),
        Command(
            "Toggle Queue Inputs",
            cmd_toggle_queue_inputs,
            "Queue or cancel on input during streaming",
            group="System",
        ),
    ]
