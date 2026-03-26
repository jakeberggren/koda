from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type ThinkingOptionId = str


class Settings(BaseModel):
    """User preferences (persisted to JSON)."""

    model_config = ConfigDict(validate_assignment=True)

    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-5.2", description="Model name")
    thinking: ThinkingOptionId = Field(
        default="none",
        description="Model thinking effort for supported reasoning models.",
    )
    theme: Literal["dark", "light"] = Field(default="dark", description="UI theme")
    show_scrollbar: bool = Field(default=True, description="Show chat scrollbar")
    queue_inputs: bool = Field(default=True, description="Queue inputs during streaming")
    allow_web_search: bool = Field(
        default=False,
        description=(
            "Allow supported models to use web search when available. This may improve "
            "freshness and factual grounding for time-sensitive questions, but can increase "
            "latency and send search queries to external services."
        ),
    )
    allow_extended_prompt_retention: bool = Field(
        default=False,
        description=(
            "Allow supported providers to use extended prompt retention to improve cache "
            "hit rates, reduce token usage, and lower costs. Enabling this may store "
            "prompt data beyond ephemeral processing and is not compatible with Zero "
            "Data Retention (ZDR) requirements."
        ),
    )


class EnvSettings(BaseSettings):
    """Environment variables for settings overrides, API keys, and runtime flags.

    Setting overrides (T | None, None = don't override):
    - KODA_<field> maps to Settings.<field> (auto-mapped)

    API keys (override keychain):
    - <PROVIDER>_API_KEY -> cached for provider

    Flags (T with default, not persisted):
    - Runtime behavior flags
    """

    # Setting overrides (KODA_<field> -> <field>, None = don't override)
    koda_provider: str | None = Field(default=None, description="LLM provider")
    koda_model: str | None = Field(default=None, description="Model name")
    koda_thinking: ThinkingOptionId | None = Field(
        default=None,
        description="Model thinking effort for supported reasoning models.",
    )
    koda_allow_web_search: bool | None = Field(
        default=None,
        description=(
            "Allow supported models to use web search when available. This may improve "
            "freshness and factual grounding for time-sensitive questions, but can increase "
            "latency and send search queries to external services."
        ),
    )
    koda_allow_extended_prompt_retention: bool | None = Field(
        default=None,
        description=(
            "Allow supported providers to use extended prompt retention to improve cache "
            "hit rates, reduce token usage, and lower costs. Enabling this may store "
            "prompt data beyond ephemeral processing and is not compatible with Zero "
            "Data Retention (ZDR) requirements."
        ),
    )

    # API keys (override keychain, cached in manager)
    openai_api_key: SecretStr | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: SecretStr | None = Field(default=None, description="Anthropic API key")
    bergetai_api_key: SecretStr | None = Field(default=None, description="BergetAI API key")

    # Flags
    koda_service: Literal["in_process"] = Field(
        default="in_process",
        description="Koda Service boundary selection for Koda clients",
    )

    # Logging
    koda_log_enabled: bool = Field(default=True, description="Enable logging")
    koda_log_level: LogLevel = Field(default="INFO", description="Log level")
    koda_log_file: Path | None = Field(default=None, description="Log file path")

    # Telemetry
    langfuse_tracing_enabled: bool = Field(default=True, description="Enable telemetry")
    langfuse_secret_key: SecretStr | None = Field(default=None, description="Langfuse secret key")
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key")
    langfuse_base_url: AnyHttpUrl | None = Field(default=None, description="Langfuse base URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
