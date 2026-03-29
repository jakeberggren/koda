from __future__ import annotations

from pathlib import Path


def koda_home_dir() -> Path:
    """Return the user-scoped Koda home directory."""
    return Path.home() / ".koda"


def config_file_path() -> Path:
    """Return the default config file path."""
    return koda_home_dir() / "config.json"


def log_dir_path() -> Path:
    """Return the default log directory."""
    return koda_home_dir() / "log"


def log_file_path(app_name: str) -> Path:
    """Return the default log file path for an app."""
    filename = f"{app_name}.log"
    return log_dir_path() / filename


def sessions_dir_path() -> Path:
    """Return the default session storage directory."""
    return koda_home_dir() / "sessions"
