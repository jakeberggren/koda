"""Pytest configuration and shared fixtures."""

from io import StringIO

import pytest
from rich.console import Console

from koda_tui.renderer import RichRenderer


@pytest.fixture
def captured_console() -> Console:
    """A Console that captures output to a StringIO for testing."""
    return Console(file=StringIO(), force_terminal=True, width=80)


@pytest.fixture
def renderer(captured_console: Console) -> RichRenderer:
    """A RichRenderer with captured output for testing."""
    return RichRenderer(console=captured_console)


def get_output(console: Console) -> str:
    """Extract the captured output from a Console."""
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue()
