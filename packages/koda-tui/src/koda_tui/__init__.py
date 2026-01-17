import asyncio

from koda_tui.app import KodaTuiApp, create_app_config
from koda_tui.clients import MockClient

__all__ = ["KodaTuiApp", "main"]


def main() -> None:
    config = create_app_config()
    app = KodaTuiApp(config=config, client=MockClient())
    asyncio.run(app.run())
