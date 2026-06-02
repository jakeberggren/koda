from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ApiKeyCredential(BaseModel):
    type: Literal["api_key"]
    value: str


class OAuthCredential(BaseModel):
    type: Literal["oauth"]
    access_token: str
    refresh_token: str
    expires_at: str
    metadata: dict[str, str] = Field(default_factory=dict)


ProviderCredential = Annotated[ApiKeyCredential | OAuthCredential, Field(discriminator="type")]
