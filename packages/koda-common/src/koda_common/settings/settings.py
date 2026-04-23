from __future__ import annotations

from typing import Literal

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from koda_common.settings.errors import DockerImageRequiredError

type ThinkingOptionId = str
type ExecutionSandox = Literal["host", "docker"]


class Settings(BaseSettings):
    """Validated shared runtime settings with env precedence over persisted values."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    provider: str | None = Field(
        default=None,
        description="LLM provider",
        validation_alias=AliasChoices("provider", "KODA_PROVIDER"),
    )
    model: str | None = Field(
        default=None,
        description="Model name",
        validation_alias=AliasChoices("model", "KODA_MODEL"),
    )
    thinking: ThinkingOptionId = Field(
        default="none",
        description="Model thinking effort for supported reasoning models.",
        validation_alias=AliasChoices("thinking", "KODA_THINKING"),
    )
    allow_web_search: bool = Field(
        default=False,
        description=(
            "Allow supported models to use web search when available. This may improve "
            "freshness and factual grounding for time-sensitive questions, but can increase "
            "latency and send search queries to external services."
        ),
        validation_alias=AliasChoices("allow_web_search", "KODA_ALLOW_WEB_SEARCH"),
    )
    allow_extended_prompt_retention: bool = Field(
        default=False,
        description=(
            "Allow supported providers to use extended prompt retention to improve cache "
            "hit rates, reduce token usage, and lower costs. Enabling this may store "
            "prompt data beyond ephemeral processing and is not compatible with Zero "
            "Data Retention (ZDR) requirements."
        ),
        validation_alias=AliasChoices(
            "allow_extended_prompt_retention",
            "KODA_ALLOW_EXTENDED_PROMPT_RETENTION",
        ),
    )
    bash_execution_sandbox: ExecutionSandox = Field(
        default="host",
        description="Command execution backend.",
        validation_alias=AliasChoices("bash_execution_sandbox", "KODA_BASH_EXECUTION_SANDBOX"),
    )
    bash_execution_docker_image: str | None = Field(
        default=None,
        description=(
            "Docker image used when bash execution sandbox is set to docker. The image "
            "should provide bash plus any tooling you want available inside the sandbox, "
            "for example Python and uv."
        ),
        validation_alias=AliasChoices(
            "bash_execution_docker_image",
            "KODA_BASH_EXECUTION_DOCKER_IMAGE",
        ),
    )
    langfuse_tracing_enabled: bool = Field(default=True, description="Enable telemetry")
    langfuse_secret_key: SecretStr | None = Field(default=None, description="Langfuse secret key")
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key")
    langfuse_base_url: AnyHttpUrl | None = Field(default=None, description="Langfuse base URL")

    @model_validator(mode="after")
    def validate_bash_execution_docker_settings(self) -> Settings:
        if self.bash_execution_sandbox == "docker" and not self.bash_execution_docker_image:
            raise DockerImageRequiredError
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del settings_cls
        return (env_settings, dotenv_settings, init_settings, file_secret_settings)


class PersistedSettings(BaseModel):
    """Persisted subset of shared runtime settings stored in the JSON config."""

    model_config = ConfigDict(validate_assignment=True)

    provider: str | None = None
    model: str | None = None
    thinking: ThinkingOptionId = "none"
    allow_web_search: bool = False
    allow_extended_prompt_retention: bool = False
    bash_execution_sandbox: ExecutionSandox = "host"
    bash_execution_docker_image: str | None = None
