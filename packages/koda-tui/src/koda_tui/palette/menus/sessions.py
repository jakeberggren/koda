"""Session palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.sessions import Session
    from koda_tui.palette.palette import Palette


log = get_logger(__name__)

_TITLE = "List Sessions"
_LIST_HEADING = "Select New Session"
_FOOTER: StyleAndTextTuples = [
    ("class:palette.item", "ctrl-n"),
    ("class:palette.hint", " new · "),
    ("class:palette.item", "ctrl-d"),
    ("class:palette.hint", " delete"),
]


class SessionMenu:
    """Session submenu behavior."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._service = palette.service
        self._state = palette.state

    def items(self) -> list[ListItem]:
        """Build session selection items."""
        return [
            ListItem(
                id=f"switch_session:{session.session_id}",
                label=_format_session_label(session),
                data=session,
            )
            for session in self._service.list_sessions()
        ]

    def open(self) -> None:
        """Open the session selection submenu."""
        self._palette.open_palette(
            self.items(),
            title=_TITLE,
            list_heading=_LIST_HEADING,
            footer=_FOOTER,
            shortcuts={
                "c-n": lambda _item: self.new(),
                "c-d": self.confirm_delete,
            },
        )

    def new(self) -> None:
        """Create and switch to a new session."""
        self._palette.cancel_streaming()
        result = actions.new_session(self._service, self._state)
        if not result.ok:
            log.warning("new_session_failed", error=result.error)
        self._palette.close_all_overlays()

    def switch(self, session: Session) -> None:
        """Switch to an existing session."""
        self._palette.cancel_streaming()
        result = actions.switch_session(session.session_id, self._service, self._state)
        if not result.ok:
            log.warning("switch_session_failed", session_id=str(session.session_id))
            return
        self._palette.close_all_overlays()

    def confirm_delete(self, item: ListItem | None) -> None:
        """Open the delete confirmation dialog for a session item."""
        if item is None or item.data is None:
            return
        session: Session = item.data
        self._palette.open_confirm(
            message="Delete session?",
            on_confirm=lambda: self.delete(session),
        )

    def delete(self, session: Session) -> None:
        """Delete a session."""
        result = actions.delete_session(session.session_id, self._service, self._state)
        if not result.ok:
            log.warning("delete_session_failed", session_id=str(session.session_id))
            return
        self._palette.close_all_overlays()


def _format_session_label(session: Session) -> str:
    timestamp = session.created_at.strftime("%Y-%m-%d")
    return f"{session.display_name}  [{timestamp}] ({session.message_count} messages)"
