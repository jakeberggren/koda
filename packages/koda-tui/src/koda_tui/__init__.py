import asyncio

from koda_tui.app import KodaTuiApp, create_app_config

__all__ = ["KodaTuiApp", "main"]


def main() -> None:
    config = create_app_config()
    app = KodaTuiApp(config=config)
    asyncio.run(app.run())
