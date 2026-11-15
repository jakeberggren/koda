from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from koda.agent import Turn
from koda.sessions import Session
from koda_tui.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm import Model, Provider


@dataclass(frozen=True, slots=True)
class TurnError:
    """A turn that failed with ``error``, after the first ``at`` messages of the session."""

    at: int
    error: Exception


@dataclass(frozen=True, slots=True)
class PendingInput:
    """A message waiting to be sent: queued behind the response, or steering into it."""

    text: str
    steer: bool = False


@dataclass
class AppState:
    """Shared application state as single source of truth for the UI."""

    workspace: Path
    settings: Settings = field(default_factory=Settings)
    session: Session = field(default_factory=Session)  # The conversation on screen.
    issue: str | None = None  # What stops Koda from responding; None when it can.
    warnings: list[str] = field(default_factory=list)
    turn: Turn = field(default_factory=Turn)  # The agent's latest.
    errors: list[TurnError] = field(default_factory=list)  # Turns that failed in this session.
    pending_inputs: list[PendingInput] = field(default_factory=list)  # Steers first.
    active_model: Model | None = None
    configured_providers: list[Provider] = field(default_factory=list)
    exit_requested: bool = False
