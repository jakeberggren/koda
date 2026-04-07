from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.ui.palette.commands import (
    model_commands,
    provider_commands,
    session_commands,
    thinking_commands,
)
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_common.settings import SettingsManager
    from koda_service import CatalogService
    from koda_service.types import ModelDefinition, ProviderDefinition
    from koda_tui.bootstrap.manager import KodaRuntimeManager
    from koda_tui.state import AppState
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)


def _has_connected_provider(
    catalog_service: CatalogService[ProviderDefinition, ModelDefinition],
) -> bool:
    return bool(catalog_service.list_connected_providers())


def get_commands(  # noqa: C901, PLR0913 - palette root assembly is intentionally centralized
    catalog_service: CatalogService[ProviderDefinition, ModelDefinition],
    settings: SettingsManager,
    state: AppState,
    palette_manager: PaletteManager,
    runtime_manager: KodaRuntimeManager,
    cancel_streaming: Callable[[], None],
) -> list[Command]:
    """Get the root palette commands."""

    def cmd_connect_provider() -> None:
        commands = provider_commands.get_commands(
            catalog_service=catalog_service,
            settings=settings,
            palette_manager=palette_manager,
        )
        palette_manager.open_palette(commands)

    def cmd_switch_model() -> None:
        commands = model_commands.get_commands(
            catalog_service=catalog_service,
            settings=settings,
            palette_manager=palette_manager,
        )
        palette_manager.open_palette(commands)

    def cmd_set_thinking() -> None:
        commands = thinking_commands.get_commands(
            catalog_service=catalog_service,
            settings=settings,
            palette_manager=palette_manager,
        )
        palette_manager.open_palette(commands)

    def cmd_toggle_theme() -> None:
        result = actions.toggle_theme(settings)
        if not result.ok:
            log.warning("cmd_toggle_theme_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_toggle_scrollbar() -> None:
        result = actions.toggle_scrollbar(settings)
        if not result.ok:
            log.warning("cmd_toggle_scrollbar_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_toggle_queue_inputs() -> None:
        result = actions.toggle_queue_inputs(settings)
        if not result.ok:
            log.warning("cmd_toggle_queue_inputs_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_new_session() -> None:
        cancel_streaming()
        runtime = runtime_manager.get_runtime()
        result = actions.new_session(runtime, state)
        if not result.ok:
            log.warning("cmd_new_session_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_list_sessions() -> None:
        session_commands.open_session_list(
            runtime_manager,
            state,
            palette_manager,
            cancel_streaming,
        )

    commands = [
        Command(
            "Connect Provider",
            cmd_connect_provider,
            "Configure LLM provider API keys",
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

    if _has_connected_provider(catalog_service):
        commands.insert(
            1,
            Command(
                "Switch Model",
                cmd_switch_model,
                "Select a different model",
                group="Agent",
            ),
        )

    if state.service_status.is_ready:
        agent_commands: list[Command] = []
        if state.thinking_supported:
            agent_commands.append(
                Command(
                    "Set Thinking Level",
                    cmd_set_thinking,
                    "Select model reasoning effort",
                    group="Agent",
                )
            )

        session_root_commands = [
            Command(
                "New Session",
                cmd_new_session,
                "Start a new conversation",
                group="Sessions",
            ),
            Command(
                "List Sessions",
                cmd_list_sessions,
                "Switch between sessions",
                group="Sessions",
            ),
        ]
        commands[1:1] = [*agent_commands, *session_root_commands]

    return commands
