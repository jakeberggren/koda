"""Palette context: what the palette's menus work with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koda_service import KodaService
    from koda_tui.messaging import Conversation, Outbox
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState
    from koda_tui.terminal import Terminal
    from koda_tui.ui.overlays import Overlays


@dataclass(frozen=True, slots=True)
class PaletteContext:
    """Where menus open their pickers and dialogs, and the parts of Koda they act on."""

    overlays: Overlays
    service: KodaService
    settings: AppSettings
    state: AppState
    conversation: Conversation
    outbox: Outbox
    terminal: Terminal
