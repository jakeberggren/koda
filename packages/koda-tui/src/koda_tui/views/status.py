"""Status: the status bar and the activity indicator shown while a response runs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, HSplit, VSplit

from koda_tui.appearance import Tokens
from koda_tui.state import ResponsePhase
from koda_tui.ui.primitives import Spacer, Spinner, Text
from koda_tui.ui.widgets import Bar

if TYPE_CHECKING:
    from koda_tui.state import AppState
    from koda_tui.ui.widgets import Segment

ACTIVITY_TEXT = "Working... (esc to interrupt)"
PHASES = {
    ResponsePhase.THINKING: "thinking",
    ResponsePhase.RESPONDING: "responding",
    ResponsePhase.WORKING: "working",
}


class StatusBar:
    """Where you are and what the model is doing: workspace, model and usage on the
    left; key hints, warnings and activity on the right."""

    def __init__(self, state: AppState) -> None:
        self._bar = Bar(left=lambda: _left(state), right=lambda: _right(state))

    def __pt_container__(self) -> Bar:
        return self._bar


class ActivityIndicator:
    """A spinner and a hint, with a gap below, shown while a response is running."""

    def __init__(self, state: AppState) -> None:
        row = VSplit(
            [
                Spinner(style=Tokens.Text.INFO),
                Text(f" {ACTIVITY_TEXT}", style=Tokens.Text.MUTED),
            ],
        )
        self._container = ConditionalContainer(
            HSplit([row, Spacer()]),
            filter=Condition(lambda: state.responding),
        )

    def __pt_container__(self) -> ConditionalContainer:
        return self._container


def _left(state: AppState) -> list[Segment]:
    return [_location(state), *_model(state), *_context(state), *_tokens(state)]


def _right(state: AppState) -> list[Segment]:
    return [*_hints(state), *_warning(state), _activity(state)]


def _location(state: AppState) -> Segment:
    """The workspace, relative to the home directory when it is inside it."""
    root = state.workspace
    try:
        path = f"~/{root.relative_to(Path.home())}"
    except ValueError:
        path = f"~/{root.name}"
    return [(Tokens.Text.MUTED, path)]


def _model(state: AppState) -> list[Segment]:
    """The provider and model, then the thinking level when one is set."""
    segments: list[Segment] = []
    if state.active_model is not None:
        model = state.active_model
        segments.append([(Tokens.Text.MUTED, f"{model.provider} · {model.name}")])
    if state.thinking.id != "none":
        segments.append([(Tokens.Text.WARNING, state.thinking.label.lower())])
    return segments


def _context(state: AppState) -> list[Segment]:
    """How full the context window is, once it is known."""
    if state.usage is None:
        return []
    percentage = state.usage.latest.context_window_percentage(state.context_window)
    return [] if percentage is None else [[(Tokens.Text.MUTED, f"ctx {percentage}%")]]


def _tokens(state: AppState) -> list[Segment]:
    """The tokens sent and received so far in this session."""
    if state.usage is None:
        return []
    total = state.usage.total
    counts = (total.input_tokens, "in"), (total.output_tokens, "out")
    return [
        [(Tokens.Text.MUTED, f"{_compact(count)} {label}")]
        for count, label in counts
        if count is not None
    ]


def _hints(state: AppState) -> list[Segment]:
    """Key bindings worth knowing, each as the key followed by what it does."""
    hints = [("ctrl+p/k", "palette")]
    if state.thinking_supported:
        hints.insert(0, ("ctrl+t", "thinking"))
    return [
        [(Tokens.Text.DEFAULT, key), (Tokens.Text.MUTED, f" {action}")] for key, action in hints
    ]


def _warning(state: AppState) -> list[Segment]:
    """The first startup warning, if there is one."""
    return [[(Tokens.Text.WARNING, state.warnings[0])]] if state.warnings else []


def _activity(state: AppState) -> Segment:
    """What Koda is doing now, or why it can't."""
    if state.exit_requested:
        return [(Tokens.Text.ACCENT, "press ctrl+c again to exit")]
    if not state.service_status.is_ready:
        return [(Tokens.Text.WARNING, state.service_status.summary)]
    return [(Tokens.Text.ACCENT, _phase(state))]


def _phase(state: AppState) -> str:
    """The stage of the current response, or "ready" between responses."""
    return PHASES.get(state.response_phase, "ready")


def _compact(count: int) -> str:
    """A token count in short form: 950, 15.9k, 1.2M."""
    for threshold, suffix in ((1_000_000, "M"), (1_000, "k")):
        if count >= threshold:
            return f"{count / threshold:.1f}".rstrip("0").rstrip(".") + suffix
    return str(count)
