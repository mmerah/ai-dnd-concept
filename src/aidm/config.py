from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self

from dotenv import set_key, unset_key
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["openrouter", "local"]
# Each role is a one-shot CLI the app spawns, so a role is only a name and a command.
Role = Literal["master", "narrator", "worldsmith"]
ENV_FILE = ".env"


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: SecretStr


class RoleConfig(BaseModel):
    """How to spawn one role. An empty `command` reuses the master's."""

    model_config = ConfigDict(frozen=True)

    # The whole command, model flag included: only the CLI knows how it names its own models.
    command: str = ""
    timeout: float = Field(default=300.0, gt=0.0)


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

    # How many past exchanges a role is shown; every role reads the same depth.
    recent_exchanges: int = Field(default=20, ge=1)


class SourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # This ~30k-token ceiling admits a 76-page adventure without swallowing the context.
    max_chars: int = Field(default=120_000, ge=1)


class Roles(BaseModel):
    master: RoleConfig = RoleConfig(command="claude -p --permission-mode bypassPermissions")
    narrator: RoleConfig = RoleConfig(timeout=120.0)
    # A whole scene from the source, the cast and the history: measured at 335 seconds.
    worldsmith: RoleConfig = RoleConfig(timeout=900.0)

    def for_name(self, name: Role) -> RoleConfig:
        match name:
            case "master":
                found = self.master
            case "narrator":
                found = self.narrator
            case "worldsmith":
                found = self.worldsmith
        return found if found.command else found.model_copy(update={"command": self.master.command})


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
    roles: Roles = Roles()
    media: MediaConfig = MediaConfig()
    turn: TurnConfig = TurnConfig()
    source: SourceConfig = SourceConfig()
    # `.mcp.json` and `.codex/config.toml` hard-code this port: change all three together.
    # Not `PORT`: that name is set in too many shells to be safe to read.
    server_port: int = Field(default=8080, gt=0, lt=65536)
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")
    packs_dir: Path = Path("packs")

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
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
