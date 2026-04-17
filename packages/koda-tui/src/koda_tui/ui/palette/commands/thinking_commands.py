from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_service.types import ThinkingOption, ThinkingOptionId


def _format_label(option: ThinkingOption, active_thinking: ThinkingOptionId) -> str:
    """Format a thinking option label with active status."""

    label = option.label
    if active_thinking == option.id:
        label += " [active]"
    return label


def get_commands(
    options: list[ThinkingOption],
    active_thinking: ThinkingOptionId,
    on_select: Callable[[ThinkingOptionId], None],
) -> list[Command]:
    """Build commands for the thinking selection palette."""

    return [
        Command(
            label=_format_label(option, active_thinking),
            handler=partial(on_select, option.id),
            description=option.description or "Select model reasoning effort",
        )
        for option in options
    ]
