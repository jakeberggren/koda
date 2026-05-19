from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from koda_tui.ui.palette.commands.command import Command, CommandStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda.llm import ThinkingOption, ThinkingOptionId


def get_commands(
    options: list[ThinkingOption],
    active_thinking: ThinkingOptionId,
    on_select: Callable[[ThinkingOptionId], None],
) -> list[Command]:
    """Build commands for the thinking selection palette."""

    return [
        Command(
            label=option.label,
            handler=partial(on_select, option.id),
            description=option.description or "Select model reasoning effort",
            status=CommandStatus.CURRENT if active_thinking == option.id else None,
        )
        for option in options
    ]
