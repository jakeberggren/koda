from __future__ import annotations

from functools import partial
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
from koda_tui.utils.model_selection import find_model, supported_thinking_options

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service import KodaService
    from koda_service.types import ModelDefinition, ProviderDefinition, ThinkingOptionId
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)


def _has_connected_provider(
    service: KodaService,
) -> bool:
    return bool(service.list_connected_providers())


def _select_model(
    model: ModelDefinition,
    *,
    service: KodaService,
    app_settings: AppSettings,
    palette_manager: PaletteManager,
) -> None:
    current_models = service.list_selectable_models()
    current_model = find_model(
        current_models,
        provider=app_settings.core.provider,
        model_id=app_settings.core.model,
    )
    result = actions.select_model(current_model, model, app_settings.core)
    if not result.ok:
        log.warning("cmd_select_model_failed", model_id=model.id, provider=model.provider)
        return
    palette_manager.close_all()


def _set_thinking(
    thinking: ThinkingOptionId,
    *,
    app_settings: AppSettings,
    palette_manager: PaletteManager,
) -> None:
    result = actions.set_thinking(thinking, app_settings.core)
    if not result.ok:
        log.warning("cmd_set_thinking_failed", thinking=thinking, error=result.error)
        return
    palette_manager.close_all()


def _auto_select_first_model(
    provider: ProviderDefinition,
    *,
    service: KodaService,
    app_settings: AppSettings,
) -> bool:
    if app_settings.core.model is not None:
        return True

    provider_models = service.list_models(provider.id)
    if not provider_models:
        return True

    result = actions.select_model(
        current_model=None,
        model=provider_models[0],
        settings=app_settings.core,
    )
    if result.ok:
        return True

    log.warning(
        "cmd_auto_select_provider_model_failed",
        provider=provider.id,
        error=result.error,
    )
    return False


def _submit_provider_api_key(
    provider: ProviderDefinition,
    key: str,
    *,
    service: KodaService,
    app_settings: AppSettings,
    palette_manager: PaletteManager,
) -> None:
    result = actions.set_provider_api_key(provider.id, key, app_settings.core)
    if not result.ok:
        log.warning("cmd_set_provider_api_key_failed", provider=provider.id, error=result.error)
        return

    if not _auto_select_first_model(provider, service=service, app_settings=app_settings):
        return

    palette_manager.close_all()


def _open_api_key_dialog(
    provider: ProviderDefinition,
    *,
    service: KodaService,
    app_settings: AppSettings,
    palette_manager: PaletteManager,
) -> None:
    palette_manager.open_dialog(
        provider=provider.name,
        on_submit=partial(
            _submit_provider_api_key,
            provider,
            service=service,
            app_settings=app_settings,
            palette_manager=palette_manager,
        ),
    )


def get_commands(  # noqa: C901 - palette root assembly is intentionally centralized
    service: KodaService,
    app_settings: AppSettings,
    state: AppState,
    palette_manager: PaletteManager,
    cancel_streaming: Callable[[], None],
) -> list[Command]:
    """Get the root palette commands."""

    def cmd_connect_provider() -> None:
        providers = service.list_providers()
        connected_provider_ids = {provider.id for provider in service.list_connected_providers()}
        commands = provider_commands.get_commands(
            providers=providers,
            connected_provider_ids=connected_provider_ids,
            on_select=partial(
                _open_api_key_dialog,
                service=service,
                app_settings=app_settings,
                palette_manager=palette_manager,
            ),
        )
        palette_manager.open_palette(commands)

    def cmd_switch_model() -> None:
        models = service.list_selectable_models()
        commands = model_commands.get_commands(
            models=models,
            active_model_id=app_settings.core.model,
            on_select=partial(
                _select_model,
                service=service,
                app_settings=app_settings,
                palette_manager=palette_manager,
            ),
        )
        palette_manager.open_palette(commands)

    def cmd_set_thinking() -> None:
        active_model = find_model(
            service.list_models(app_settings.core.provider),
            provider=app_settings.core.provider,
            model_id=app_settings.core.model,
        )
        options = supported_thinking_options(active_model)
        commands = thinking_commands.get_commands(
            options=options,
            active_thinking=app_settings.core.thinking,
            on_select=partial(
                _set_thinking,
                app_settings=app_settings,
                palette_manager=palette_manager,
            ),
        )
        palette_manager.open_palette(commands)

    def cmd_toggle_theme() -> None:
        result = actions.toggle_theme(app_settings.tui)
        if not result.ok:
            log.warning("cmd_toggle_theme_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_toggle_scrollbar() -> None:
        result = actions.toggle_scrollbar(app_settings.tui)
        if not result.ok:
            log.warning("cmd_toggle_scrollbar_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_toggle_queue_inputs() -> None:
        result = actions.toggle_queue_inputs(app_settings.tui)
        if not result.ok:
            log.warning("cmd_toggle_queue_inputs_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_new_session() -> None:
        cancel_streaming()
        result = actions.new_session(service, state)
        if not result.ok:
            log.warning("cmd_new_session_failed", error=result.error)
            # TODO: surface action errors in the palette/status UI.
            return
        palette_manager.close_all()

    def cmd_list_sessions() -> None:
        session_commands.open_session_list(
            service,
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

    if _has_connected_provider(service):
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
