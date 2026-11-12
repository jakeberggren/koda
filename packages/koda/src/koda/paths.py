"""Where Koda keeps its files: ``~/.koda``."""

from pathlib import Path


def koda_home_dir() -> Path:
    """The user's Koda directory."""
    return Path.home() / ".koda"


def sessions_dir_path() -> Path:
    """Where sessions are saved."""
    return koda_home_dir() / "sessions"


def model_overrides_file_path() -> Path:
    """The user's models.json, which adds to and overrides the bundled catalog."""
    return koda_home_dir() / "models.json"
