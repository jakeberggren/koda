"""Application-specific palette controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.palette.menus.models import ModelMenu
from koda_tui.palette.menus.providers import ProviderMenu
from koda_tui.palette.menus.sessions import SessionMenu
from koda_tui.palette.menus.thinking import ThinkingMenu
from koda_tui.palette.root import RootMenu

if TYPE_CHECKING:
    from typing import Any

    from koda_tui.palette.items import ListItem
    from koda_tui.palette.palette import Palette


log = get_logger(__name__)


class PaletteController:
    """Coordinates top-level palette items and submenu actions."""

    def __init__(self, app: Palette) -> None:
        self._app = app
        self._settings = app.app_settings
        self.root = RootMenu(app.service, app.state)
        self.providers = ProviderMenu(app)
        self.models = ModelMenu(app)
        self.thinking = ThinkingMenu(app)
        self.sessions = SessionMenu(app)

    def _execute_with_param(self, base_id: str, param: str, data: Any) -> None:
        match base_id:
            case "select_provider":
                self.providers.select(data)
            case "select_model":
                self.models.select(data)
            case "select_thinking":
                self.thinking.select(data)
            case "switch_session":
                self.sessions.switch(data)
            case _:
                log.warning("unknown_palette_item", base_id=base_id, param=param)

    def _toggle_theme(self) -> None:
        result = actions.toggle_theme(self._settings.tui)
        if not result.ok:
            log.warning("toggle_theme_failed", error=result.error)
        self._app.close_all_overlays()

    def _toggle_scrollbar(self) -> None:
        result = actions.toggle_scrollbar(self._settings.tui)
        if not result.ok:
            log.warning("toggle_scrollbar_failed", error=result.error)
        self._app.close_all_overlays()

    def _toggle_queue_inputs(self) -> None:
        result = actions.toggle_queue_inputs(self._settings.tui)
        if not result.ok:
            log.warning("toggle_queue_inputs_failed", error=result.error)
        self._app.close_all_overlays()

    def root_items(self) -> list[ListItem]:
        """Build the top-level palette items."""
        return self.root.items()

    def execute(self, item: ListItem) -> None:  # noqa: C901
        """Execute the action represented by a selected palette item."""
        if ":" in item.id:
            base_id, param = item.id.split(":", 1)
            self._execute_with_param(base_id, param, item.data)
            return

        match item.id:
            case "connect_provider":
                self.providers.open()
            case "switch_model":
                self.models.open()
            case "set_thinking":
                self.thinking.open()
            case "toggle_theme":
                self._toggle_theme()
            case "toggle_scrollbar":
                self._toggle_scrollbar()
            case "toggle_queue_inputs":
                self._toggle_queue_inputs()
            case "new_session":
                self.sessions.new()
            case "list_sessions":
                self.sessions.open()
            case _:
                log.warning("unknown_palette_item", item_id=item.id)
