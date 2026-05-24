"""Protocol for modal overlay content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import AnyContainer

    FocusTarget = Buffer | AnyContainer


@runtime_checkable
class Overlay(Protocol):
    """Content that can be mounted inside an :class:`OverlayManager` float."""

    @property
    def focus_target(self) -> FocusTarget:
        """Prompt_toolkit target to focus while this overlay is active."""
        ...

    def __pt_container__(self) -> AnyContainer:
        """Return the prompt_toolkit container rendered inside the float."""
        ...
