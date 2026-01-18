from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseModel):
    """Application settings. Add new fields here with defaults."""

    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-5.2", description="Model name")
    use_mock_client: bool = Field(default=False, description="Use mock client for testing")
    api_keys: dict[str, str] = Field(
        default_factory=dict,
        description="API keys per provider",
        exclude=True,  # Don't serialize to JSON (stored in keychain)
    )


class EnvSettings(BaseSettings):
    """Environment variable overrides. These take precedence over other settings.

    Naming convention:
    - KODA_<field> maps to Settings.<field> (auto-mapped)
    - <PROVIDER>_API_KEY maps to api_keys[provider] (special case)
    """

    # Auto-mapped settings (KODA_<field> -> <field>)
    koda_provider: str | None = Field(default=None, description="LLM provider")
    koda_model: str | None = Field(default=None, description="Model name")
    koda_use_mock_client: bool | None = Field(default=None, description="Use mock client")

    # API keys (special case - stored in keychain, env overrides)
    openai_api_key: SecretStr | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: SecretStr | None = Field(default=None, description="Anthropic API key")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
