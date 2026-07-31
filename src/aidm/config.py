from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from aidm_5e.config import Dnd5eConfig

from .domain.base import ROLES, Role

ProviderName = Literal["openrouter", "local"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: SecretStr


class RoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    model: str
    retries: int = Field(ge=0)
    max_tokens: int = Field(ge=1)
    reasoning_effort: ReasoningEffort


class Providers(BaseModel):
    openrouter: ProviderConfig = ProviderConfig(
        base_url="https://openrouter.ai/api/v1",
        api_key=SecretStr(""),
    )
    local: ProviderConfig = ProviderConfig(
        base_url="http://localhost:11434/v1",
        api_key=SecretStr("none"),
    )

    def for_name(self, name: ProviderName) -> ProviderConfig:
        match name:
            case "openrouter":
                return self.openrouter
            case "local":
                return self.local


DEFAULT_ROLE = RoleConfig(
    provider="openrouter",
    model="openai/gpt-oss-120b",
    retries=3,
    max_tokens=2048,
    reasoning_effort="medium",
)


class Roles(BaseModel):
    director: RoleConfig = DEFAULT_ROLE
    narrator: RoleConfig = DEFAULT_ROLE
    maintainer: RoleConfig = DEFAULT_ROLE
    creator: RoleConfig = DEFAULT_ROLE

    def for_role(self, role: Role) -> RoleConfig:
        match role:
            case "director":
                return self.director
            case "narrator":
                return self.narrator
            case "maintainer":
                return self.maintainer
            case "creator":
                return self.creator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    providers: Providers = Providers()
    roles: Roles = Roles()
    dnd5e: Dnd5eConfig = Field(default_factory=Dnd5eConfig)
    max_growth: int = Field(default=3, ge=0)
    history_window: int = Field(default=6, ge=0)
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
        for role in ROLES:
            provider_name = self.roles.for_role(role).provider
            provider = self.providers.for_name(provider_name)
            if not provider.api_key.get_secret_value():
                raise ValueError(
                    f"role {role!r} uses provider {provider_name!r}, which has no api_key"
                )
        return self
