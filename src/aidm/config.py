from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self, get_args

from dotenv import set_key, unset_key
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["openrouter", "local"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
# A stage is built by name, so an unbuildable role cannot be configured.
Role = Literal["director", "narrator", "scenario_creator"]
ENV_FILE = ".env"
BUILTIN_ONLY: dict[str, JsonValue] = {"applies": "builtin"}
CODE_MODE_ONLY: dict[str, JsonValue] = {"applies": "code mode"}


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: SecretStr


class RoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: ProviderName = "openrouter"
    model: str = "deepseek/deepseek-v4-flash-0731:nitro"
    retries: int = Field(default=3, ge=0)
    max_tokens: int = Field(default=4096, ge=1)
    reasoning_effort: ReasoningEffort = "minimal"
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class MediaConfig(BaseModel):
    """Media is optional presentation, so failures only log and the default is off."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    provider: ProviderName = "openrouter"
    model: str = "google/gemini-3.1-flash-lite-image"
    scene_ratio: str = "16:9"
    icon_ratio: str = "1:1"
    timeout: float = Field(default=180.0, gt=0.0)
    max_references: int = Field(default=4, ge=0)
    style: str = "Painterly fantasy illustration, muted colours, no text or lettering."


class TurnConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    director_request_limit: int = Field(default=16, ge=1, json_schema_extra=BUILTIN_ONLY)
    # How many past exchanges an agent is shown; every harness reads the same depth.
    recent_exchanges: int = Field(default=20, ge=1)
    # Which model an agent harness plays on. Empty leaves the choice to the agent's own config.
    harness_model: str = Field(default="", json_schema_extra=CODE_MODE_ONLY)


class SourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # This ~30k-token ceiling admits a 76-page adventure without swallowing the context.
    max_chars: int = Field(default=120_000, ge=1)


class Roles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Tool loops divide the budget across calls and need reasoning to choose among tools.
    director: RoleConfig = RoleConfig(max_tokens=8192, reasoning_effort="low")
    narrator: RoleConfig = RoleConfig()
    scenario_creator: RoleConfig = RoleConfig(max_tokens=32768, reasoning_effort="medium")

    def for_name(self, name: Role) -> RoleConfig:
        match name:
            case "director":
                return self.director
            case "narrator":
                return self.narrator
            case "scenario_creator":
                return self.scenario_creator


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
        env_file=ENV_FILE,
        extra="ignore",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    providers: Providers = Providers()
    roles: Roles = Field(default=Roles(), json_schema_extra=BUILTIN_ONLY)
    media: MediaConfig = MediaConfig()
    turn: TurnConfig = TurnConfig()
    source: SourceConfig = SourceConfig()
    # Who plays the turn: the app's own roles, an agent you run yourself, or one the app launches.
    harness: Literal["builtin", "external", "claude", "codex"] = "builtin"
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")
    packs_dir: Path = Path("packs")

    @property
    def code_mode(self) -> bool:
        return self.harness != "builtin"

    def role(self, name: Role) -> RoleConfig:
        found = self.roles.for_name(name)
        if not self.providers.for_name(found.provider).api_key.get_secret_value():
            raise ValueError(
                f"role {name!r} uses provider {found.provider!r}, which has no api_key"
            )
        return found

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
        # One `ROLES__*` env var fills all four, so only a role off its default was configured.
        defaults = Roles()
        for name in get_args(Role):
            if self.roles.for_name(name) != defaults.for_name(name):
                _ = self.role(name)
        if self.media.enabled and not self.providers.for_name(self.media.provider).api_key:
            raise ValueError(f"media uses provider {self.media.provider!r}, which has no api_key")
        return self


def load_settings() -> Settings:
    return Settings.model_validate({})


def env_key(path: tuple[str, ...]) -> str:
    return "__".join(path).upper()


def save_settings(changed: Mapping[tuple[str, ...], str | None]) -> None:
    """`set_key` rewrites one line in place, so comments and untouched keys survive."""
    for path, value in changed.items():
        if value is None:
            unset_key(ENV_FILE, env_key(path))
        else:
            set_key(ENV_FILE, env_key(path), value)
