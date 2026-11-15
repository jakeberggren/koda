"""Hooks: what else happens as the agent works."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koda.sessions import Session


class Hook:
    """Something to do as the agent works. Override what you need; the rest do nothing.

    An error in a hook ends the turn as failed.
    """

    async def on_checkpoint(self, session: Session) -> None:
        """The session changed in a way worth keeping: a message was added or a turn ended."""
