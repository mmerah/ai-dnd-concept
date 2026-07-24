"""Runtime configuration, loaded once from .env. Paths are relative to the working directory.

Per-role model, endpoint, retries, token budget and reasoning level all live here, so a role's
cost and latency profile is read from one table rather than inferred from scattered constants."""

from functools import cache
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .domain.models import ROLES, Role

ProviderName = Literal["openrouter", "local"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


class ProviderConfig(BaseModel):
    """An endpoint. Keys never live in this file; they arrive from .env."""

    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: SecretStr  # keeps the key out of ValidationError reprs


class RoleConfig(BaseModel):
    """Every knob is required: a role's cost and latency profile should be read, not inferred."""

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
        match name:
            case "openrouter":
                return self.openrouter
            case "local":
                return self.local


_DEFAULT_ROLE = RoleConfig(
    provider="openrouter",
    model="openai/gpt-oss-120b",
    retries=3,  # small models mis-name things; let them be corrected instead of failing the turn
    max_tokens=2048,
    reasoning_effort="medium",
)


class Roles(BaseModel):
    """One field per `Role`. A nested model rather than a dict, because only nested models merge
    with env overrides such as `ROLES__MAINTAINER__MODEL`."""

    director: RoleConfig = _DEFAULT_ROLE
    narrator: RoleConfig = _DEFAULT_ROLE
    maintainer: RoleConfig = _DEFAULT_ROLE
    creator: RoleConfig = _DEFAULT_ROLE

    def for_role(self, role: Role) -> RoleConfig:
        """Exhaustive on purpose: a new `Role` must not silently inherit another's budget."""
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
        nested_model_default_partial_update=True,  # without this, an env override needs every field
    )

    providers: Providers = Providers()
    roles: Roles = Roles()
    max_growth: int = Field(default=3, ge=0)
    history_window: int = Field(default=6, ge=0)
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
        """Fail at startup, not on the first turn, if a role points at a keyless endpoint."""
        for role in ROLES:
            name = self.roles.for_role(role).provider
            if not self.providers.for_name(name).api_key.get_secret_value():
                raise ValueError(f"role {role!r} uses provider {name!r}, which has no api_key")
        return self


@cache
def settings() -> Settings:
    return Settings.model_validate({})
