"""Tests for the thinking-level menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm import ModelDefinition, ThinkingOption
from koda_tui.palette.menus.thinking import ThinkingMenu

if TYPE_CHECKING:
    from unittest.mock import Mock

    from tests.palette.conftest import Overlays

    from koda_tui.palette.context import PaletteContext


def test_lists_the_models_levels_and_sets_the_chosen_one(
    context: PaletteContext, overlays: Overlays, settings: Mock
) -> None:
    context.state.active_model = ModelDefinition(
        id="m",
        name="Model",
        provider="p",
        thinking_options=[
            ThinkingOption(id="none", label="None"),
            ThinkingOption(id="high", label="High"),
        ],
    )
    settings.core.thinking = "none"
    ThinkingMenu(context).open()

    items = overlays.stack[-1]["items"]
    assert [(item.label, item.current) for item in items] == [("None", True), ("High", False)]
    overlays.pick("High")
    settings.core.set.assert_called_once_with("thinking", "high")


def test_without_a_model_there_are_no_levels(context: PaletteContext, overlays: Overlays) -> None:
    context.state.active_model = None
    ThinkingMenu(context).open()
    assert overlays.stack[-1]["items"] == []
