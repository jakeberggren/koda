"""Icons shared by every theme: symbols that stand for something, and marks drawn
around text. Each is one cell wide; whatever draws one adds its own spacing."""

from __future__ import annotations


class Icons:
    RUNNING = "●"  # A tool call still running.
    FAILED = "✕"  # A tool call that failed.
    DONE = "✓"  # A tool call that finished, or a provider that is connected.
    CURRENT = "*"  # The list item in use now, such as the active model.
    SELECTED = "-"  # The list item the selection is on.
    PROMPT = "❯"  # noqa: RUF001 - the prompt mark, not a typo for ">"
    RESULT = "└"  # Leads each line of a tool's result.
    DIVIDER = "·"  # Between status bar segments, key hints, provider and model.
    SCROLL_THUMB = "█"
    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"  # The spinner's frames, in order.
