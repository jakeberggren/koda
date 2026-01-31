from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands import model_commands, provider_commands
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common import SettingsManager
    from koda_tui.clients import Client
    from koda_tui.ui.palette.palette_manager import PaletteManager


def get_commands(
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
            settings=settings,
            palette_manager=palette_manager,
        )
        palette_manager.open_palette(commands)

    return [
        Command("Connect Provider", cmd_connect_provider, "Configure LLM provider API keys"),
        Command("Switch Model", cmd_switch_model, "Select a different model"),
    ]
