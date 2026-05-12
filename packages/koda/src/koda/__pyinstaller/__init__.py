from pathlib import Path


def get_hook_dirs() -> list[str]:
    """Return hook directories for PyInstaller to discover."""
    return [str(Path(__file__).parent)]
