"""Selectable palette item data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class ListItem:
    """A selectable item in a palette list."""

    id: str
    label: str
    detail: str = ""
    group: str | None = None
    marker: str | None = None
    marker_style: str | None = None
    data: Any = None
