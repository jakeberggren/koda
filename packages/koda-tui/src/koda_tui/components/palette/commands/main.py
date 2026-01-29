"""Main palette commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.components.palette.commands import model, provider
from koda_tui.components.palette.commands.base import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_common import SettingsManager
    from koda_tui.clients import Client
    from koda_tui.components.palette.manager import PaletteManager


def get_main_commands(
    client: Client,
    settings: SettingsManager,
    palette_manager: PaletteManager,
    on_close: Callable[[], None],
    open_palette: Callable[[list[Command]], None],
) -> list[Command]:
    """Get the main palette commands.

    Args:
        settings: Settings manager
        palette_manager: Palette manager for pushing dialogs
        on_close: Callback when overlay is closed
        open_palette: Callback to open a nested palette with commands
    """

    def cmd_connect_provider() -> None:
        commands = provider.get_provider_commands(
            client=client,
            settings=settings,
            palette_manager=palette_manager,
            on_close=on_close,
        )
        open_palette(commands)

    def cmd_switch_model() -> None:
        commands = model.get_model_commands(
            settings=settings,
            palette_manager=palette_manager,
        )
        open_palette(commands)

    return [
        Command("Connect Provider", cmd_connect_provider, "Configure LLM provider API keys"),
        Command("Switch Model", cmd_switch_model, "Select a different model"),
    ]
