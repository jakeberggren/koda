from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseModel):
    """User preferences (persisted to JSON)."""

    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-5.2", description="Model name")


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

    # API keys (override keychain, cached in manager)
    openai_api_key: SecretStr | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: SecretStr | None = Field(default=None, description="Anthropic API key")

    # Flags
    koda_use_mock_client: bool = Field(default=False, description="Use mock client for testing")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
