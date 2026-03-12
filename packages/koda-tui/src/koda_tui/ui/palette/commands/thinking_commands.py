from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_common.contracts import ThinkingLevel
from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from koda_common.contracts import KodaBackend
    from koda_common.settings import SettingsManager
    from koda_tui.ui.palette.palette_manager import PaletteManager

log = get_logger(__name__)

_THINKING_LABELS: dict[ThinkingLevel, str] = {
    ThinkingLevel.NONE: "None",
    ThinkingLevel.MINIMAL: "Minimal",
    ThinkingLevel.LOW: "Low",
    ThinkingLevel.MEDIUM: "Medium",
    ThinkingLevel.HIGH: "High",
    ThinkingLevel.XHIGH: "XHigh",
}

_THINKING_ORDER = [
    ThinkingLevel.NONE,
    ThinkingLevel.MINIMAL,
    ThinkingLevel.LOW,
    ThinkingLevel.MEDIUM,
    ThinkingLevel.HIGH,
    ThinkingLevel.XHIGH,
]


def _format_label(level: ThinkingLevel, settings: SettingsManager) -> str:
    label = _THINKING_LABELS[level]
    if settings.thinking is level:
        label += " [active]"
    return label


def _set_thinking(
    level: ThinkingLevel,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> None:
    result = actions.set_thinking(level, settings)
    if not result.ok:
        log.warning("cmd_set_thinking_failed", thinking=level.value, error=result.error)
        return
    palette_manager.close_all()


def _get_supported_thinking_levels(
    backend: KodaBackend,
    settings: SettingsManager,
) -> list[ThinkingLevel]:
    active_model = next(
        (
            model
            for model in backend.list_models(settings.provider)
            if model.provider == settings.provider and model.id == settings.model
        ),
        None,
    )
    if active_model is None:
        return [ThinkingLevel.NONE]

    supported = set(active_model.thinking)
    return [level for level in _THINKING_ORDER if level in supported]


def get_commands(
    backend: KodaBackend,
    settings: SettingsManager,
    palette_manager: PaletteManager,
) -> list[Command]:
    return [
        Command(
            label=_format_label(level, settings),
            handler=partial(_set_thinking, level, settings, palette_manager),
            description="Select model reasoning effort",
        )
        for level in _get_supported_thinking_levels(backend, settings)
    ]
