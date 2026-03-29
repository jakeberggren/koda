from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from koda_common.logging.types import LogLevel


class LoggingEnvSettings(BaseSettings):
    koda_log_enabled: bool = Field(default=True, description="Enable logging")
    koda_log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    koda_log_file: Path | None = Field(default=None, description="Log file path")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
