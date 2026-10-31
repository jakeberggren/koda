"""Tests for the input mode menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.palette.menus.input import InputMenu

if TYPE_CHECKING:
    from unittest.mock import Mock

    from tests.palette.conftest import Overlays

    from koda_tui.palette.context import PaletteContext


def test_lists_both_modes_and_sets_the_chosen_one(
    context: PaletteContext, overlays: Overlays, settings: Mock
) -> None:
    settings.tui.queue_inputs = True
    InputMenu(context).open()

    items = overlays.stack[-1]["items"]
    assert [(item.label, item.current) for item in items] == [
        ("Prefer steer", False),
        ("Prefer queue", True),
    ]
    overlays.pick("Prefer steer")
    settings.tui.set.assert_called_once_with("queue_inputs", False)  # noqa: FBT003
