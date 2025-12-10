from pydantic import Field, SecretStr
from pydantic_core import Url
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENAI_API_KEY: SecretStr = Field(
        default=SecretStr(""), description="The API key for the OpenAI API"
    )
    ANTHROPIC_API_KEY: SecretStr = Field(
        default=SecretStr(""), description="The API key for the Anthropic API"
    )
    LANGFUSE_SECRET_KEY: SecretStr = Field(
        default=SecretStr(""), description="Secret key for Langfuse observability platform"
    )
    LANGFUSE_PUBLIC_KEY: str = Field(
        default="", description="Public key for Langfuse observability platform"
    )
    LANGFUSE_BASE_URL: Url = Field(
        default=Url(url="https://cloud.langfuse.com"),
        description="Base URL for Langfuse observability platform",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
