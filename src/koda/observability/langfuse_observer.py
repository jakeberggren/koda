from __future__ import annotations

from langfuse import Langfuse

from koda.config import settings


class LangfuseObserver:
    def __init__(
        self,
        settings: settings.Settings,
    ) -> None:
        public_key = settings.LANGFUSE_PUBLIC_KEY
        secret_key = settings.LANGFUSE_SECRET_KEY
        base_url = settings.LANGFUSE_BASE_URL

        self._client = Langfuse(
            public_key=public_key,
            secret_key=secret_key.get_secret_value(),
            base_url=str(base_url),
        )

    @property
    def client(self) -> Langfuse:
        return self._client


def create_observer(settings: settings.Settings) -> LangfuseObserver:
    return LangfuseObserver(settings=settings)
