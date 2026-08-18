from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["openrouter", "local"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
# The roles a build has. A stage is built by name, so an unbuildable name cannot be configured.
Role = Literal["director", "narrator", "worldkeeper", "expander", "advisor", "scenario_creator"]


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: SecretStr


class RoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: ProviderName = "openrouter"
    model: str = "openai/gpt-oss-120b"
    retries: int = Field(default=3, ge=0)
    max_tokens: int = Field(default=2048, ge=1)
    reasoning_effort: ReasoningEffort = "low"
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class MediaConfig(BaseModel):
    """Scene illustrations: presentation only, so the default is off and a failure costs a log
    line."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    provider: ProviderName = "openrouter"
    model: str = "google/gemini-3.1-flash-lite-image"
    scene_ratio: str = "16:9"
    icon_ratio: str = "1:1"


# Authoring passes write whole records, which the turn-loop defaults cannot.
ROLE_DEFAULTS: dict[Role, RoleConfig] = {
    "expander": RoleConfig(max_tokens=8192, reasoning_effort="medium"),
    "scenario_creator": RoleConfig(max_tokens=32768, reasoning_effort="medium"),
}


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    providers: Providers = Providers()
    roles: dict[Role, RoleConfig] = Field(default_factory=dict)
    media: MediaConfig = MediaConfig()
    max_beats: int = Field(default=3, ge=1)
    max_growth: int = Field(default=3, ge=0)
    max_memories: int = Field(default=2, ge=0)
    history_window: int = Field(default=6, ge=0)
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")
    packs_dir: Path = Path("packs")

    def role(self, name: Role) -> RoleConfig:
        defaults = ROLE_DEFAULTS.get(name, RoleConfig())
        supplied = self.roles.get(name)
        # A partial override keeps the role's other defaults; model_copy would skip validation.
        found = (
            defaults
            if supplied is None
            else RoleConfig.model_validate(
                defaults.model_dump()
                | {field: getattr(supplied, field) for field in supplied.model_fields_set}
            )
        )
        if not self.providers.for_name(found.provider).api_key.get_secret_value():
            raise ValueError(
                f"role {name!r} uses provider {found.provider!r}, which has no api_key"
            )
        return found

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
        for name in self.roles:
            self.role(name)
        if self.media.enabled and not self.providers.for_name(self.media.provider).api_key:
            raise ValueError(f"media uses provider {self.media.provider!r}, which has no api_key")
        return self


def load_settings() -> Settings:
    return Settings.model_validate({})
