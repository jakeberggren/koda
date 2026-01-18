import asyncio
import sys

from koda_tui.app import KodaTuiApp

__all__ = ["KodaTuiApp", "main"]


def main() -> None:
    try:
        app = KodaTuiApp()
        asyncio.run(app.run())
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
