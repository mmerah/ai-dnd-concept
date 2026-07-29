from functools import cache
from pathlib import Path
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .domain.models.base import ROLES, Role

ProviderName = Literal["openrouter", "local"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: SecretStr  # avoids exposing keys in validation errors


class RoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    model: str
    retries: int = Field(ge=0)
    max_tokens: int = Field(ge=1)
    reasoning_effort: ReasoningEffort


class Providers(BaseModel):
    openrouter: ProviderConfig = ProviderConfig(
        base_url="https://openrouter.ai/api/v1", api_key=SecretStr("")
    )
    local: ProviderConfig = ProviderConfig(
        base_url="http://localhost:11434/v1", api_key=SecretStr("none")
    )

    def for_name(self, name: ProviderName) -> ProviderConfig:
        return cast(ProviderConfig, getattr(self, name))


_DEFAULT_ROLE = RoleConfig(
    provider="openrouter",
    model="openai/gpt-oss-120b",
    retries=3,
    max_tokens=2048,
    reasoning_effort="medium",
)


class Roles(BaseModel):
    """Uses fields because nested models support partial environment overrides."""

    director: RoleConfig = _DEFAULT_ROLE
    narrator: RoleConfig = _DEFAULT_ROLE
    maintainer: RoleConfig = _DEFAULT_ROLE
    creator: RoleConfig = _DEFAULT_ROLE

    def for_role(self, role: Role) -> RoleConfig:
        return cast(RoleConfig, getattr(self, role))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    providers: Providers = Providers()
    roles: Roles = Roles()
    max_growth: int = Field(default=3, ge=0)
    history_window: int = Field(default=6, ge=0)
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")
    # Explicit ordering keeps pack precedence deterministic.
    packs: list[Path] = [Path("packs") / "srd-2014"]

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
        for role in ROLES:
            name = self.roles.for_role(role).provider
            if not self.providers.for_name(name).api_key.get_secret_value():
                raise ValueError(f"role {role!r} uses provider {name!r}, which has no api_key")
        return self


@cache
def settings() -> Settings:
    return Settings.model_validate({})
