import asyncio

from koda_tui.app import KodaTuiApp

__all__ = ["KodaTuiApp", "main"]


def main() -> None:
    app = KodaTuiApp()
    asyncio.run(app.run())
