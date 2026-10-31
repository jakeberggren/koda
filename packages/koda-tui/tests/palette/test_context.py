"""Tests for the palette context's picker for a choice."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_tui.ui.primitives import ListItem

if TYPE_CHECKING:
    from tests.palette.conftest import Overlays

    from koda_tui.palette.context import PaletteContext


def test_choosing_passes_the_data_on_and_closes_the_palette(
    context: PaletteContext, overlays: Overlays
) -> None:
    chosen: list[int] = []
    overlays.open({"title": "the palette"})
    items = [ListItem(label="one", data=1), ListItem(label="two", data=2)]

    context.choose("Title", items, heading="Heading", on_choose=chosen.append)
    assert (overlays.stack[-1]["title"], overlays.stack[-1]["heading"]) == ("Title", "Heading")
    overlays.pick("two")

    assert chosen == [2]
    assert overlays.stack == []


def test_closing_the_picker_goes_back_one_step(context: PaletteContext, overlays: Overlays) -> None:
    overlays.open({"title": "the palette"})
    context.choose("Title", [], heading="Heading", on_choose=print)
    overlays.stack[-1]["on_close"]()
    assert overlays.stack == [{"title": "the palette"}]
