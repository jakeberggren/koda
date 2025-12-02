"""Configuration settings for the agents framework."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Settings are automatically loaded from a `.env` file if present, with
    environment variables taking precedence.
    """

    OPENAI_API_KEY: SecretStr = Field(
        default=SecretStr(""), description="The API key for the OpenAI API"
    )
    ANTHROPIC_API_KEY: SecretStr = Field(
        default=SecretStr(""), description="The API key for the Anthropic API"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
