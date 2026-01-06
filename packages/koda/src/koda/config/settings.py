from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="The API key for the OpenAI API",
    )
    ANTHROPIC_API_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="The API key for the Anthropic API",
    )
    KODA_DEFAULT_PROVIDER: str = Field(
        default="openai",
        description="The default provider to use for the Koda agent",
    )
    KODA_DEFAULT_MODEL: str = Field(
        default="gpt-5.2",
        description="The default model to use for the Koda agent",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
