from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.thinking import find_model, supported_thinking_options
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common.contracts import KodaBackend, ThinkingOption
    from koda_common.settings import SettingsManager
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)


def _format_label(option: ThinkingOption, settings: SettingsManager) -> str:
    label = option.label
    if settings.thinking == option.id:
        label += " [active]"
    return label


def _set_thinking(
    option: ThinkingOption,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    result = actions.set_thinking(option.id, settings)
    if not result.ok:
        log.warning("cmd_set_thinking_failed", thinking=option.id, error=result.error)
        return
    palette_manager.close_all()


def _get_supported_thinking_options(
    backend: KodaBackend,
    settings: SettingsManager,
) -> list[ThinkingOption]:
    active_model = find_model(
        backend.list_models(settings.provider),
        provider=settings.provider,
        model_id=settings.model,
    )
    return supported_thinking_options(active_model)


def get_commands(
    backend: KodaBackend,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    return [
        Command(
            label=_format_label(option, settings),
            handler=partial(_set_thinking, option, settings, palette_manager),
            description=option.description or "Select model reasoning effort",
        )
        for option in _get_supported_thinking_options(backend, settings)
    ]
