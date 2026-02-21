from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langfuse import Langfuse

from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda_common.settings import SettingsManager

logger = get_logger(__name__)


class LangfuseTelemetry:
    """Langfuse telemetry for provider tracing."""

    def __init__(self, langfuse_factory: Callable[..., Any] = Langfuse) -> None:
        self._langfuse_factory = langfuse_factory
        self._initialized = False

    def initialize(self, settings: SettingsManager) -> None:
        if self._initialized:
            return
        if not settings.langfuse_tracing_enabled:
            logger.info("langfuse_disabled", reason="langfuse_tracing_disabled")
            self._initialized = True
            return

        self._langfuse_factory(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key.get_secret_value()
            if settings.langfuse_secret_key
            else None,
            base_url=str(settings.langfuse_base_url) if settings.langfuse_base_url else None,
            tracing_enabled=True,
        )
        logger.info("langfuse_initialized")
        self._initialized = True
