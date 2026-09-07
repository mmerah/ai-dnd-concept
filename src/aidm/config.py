from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self

from dotenv import set_key, unset_key
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from aidm.core.entities import Frozen

type ProviderName = Literal["openrouter", "local"]
type Role = Literal["master", "narrator", "worldsmith"]
type CliProvider = Literal["claude", "codex"]
# Spelled flat, not as a union of the two: the settings page renders one `Literal` as a select.
type RoleProvider = Literal["claude", "codex", "openrouter", "local"]
type Effort = Literal["low", "medium", "high"]
ENV_FILE = ".env"


class ProviderConfig(Frozen):
    base_url: str
    api_key: SecretStr


class RoleConfig(Frozen):
    provider: RoleProvider = "claude"
    # A string, not a `Literal`: model aliases move faster than this file.
    model: str = Field(min_length=1)
    effort: Effort = "medium"
    timeout: float = Field(default=300.0, gt=0.0)
    # The replies a master may make in one turn over an API; a CLI paces itself.
    max_rounds: int = Field(default=30, gt=0)

    @property
    def cli(self) -> CliProvider | None:
        match self.provider:
            case "claude" | "codex":
                return self.provider
            case "openrouter" | "local":
                return None

    @property
    def api(self) -> ProviderName | None:
        match self.provider:
            case "claude" | "codex":
                return None
            case "openrouter" | "local":
                return self.provider


class MediaConfig(Frozen):
    enabled: bool = False
    provider: ProviderName = "openrouter"
    model: str = "google/gemini-3.1-flash-lite-image"
    scene_ratio: str = "16:9"
    icon_ratio: str = "1:1"
    timeout: float = Field(default=180.0, gt=0.0)
    max_references: int = Field(default=4, ge=0)


class SpeechConfig(Frozen):
    enabled: bool = False
    provider: ProviderName = "openrouter"
    model: str = "google/gemini-3.1-flash-tts-preview"
    # `voice` is the narrator's unless the scenario names one; `voices` is the pool to draw from.
    voice: str = "Kore"
    voices: tuple[str, ...] = Field(
        default=("Kore", "Puck", "Charon", "Zephyr", "Fenrir"), min_length=1
    )
    sample_rate: int = Field(default=24_000, gt=0)
    timeout: float = Field(default=60.0, gt=0.0)


class Roles(Frozen):
    master: RoleConfig = RoleConfig(model="opus", effort="high")
    narrator: RoleConfig = RoleConfig(model="sonnet", effort="low", timeout=120.0)
    # A whole scene from the source, the cast and the history: measured at 335 seconds.
    worldsmith: RoleConfig = RoleConfig(model="sonnet", timeout=900.0)

    def for_name(self, name: Role) -> RoleConfig:
        match name:
            case "master":
                return self.master
            case "narrator":
                return self.narrator
            case "worldsmith":
                return self.worldsmith

    def each(self) -> tuple[tuple[Role, RoleConfig], ...]:
        return (
            ("master", self.master),
            ("narrator", self.narrator),
            ("worldsmith", self.worldsmith),
        )


class Providers(Frozen):
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
    speech: SpeechConfig = SpeechConfig()
    # A party member may speak after a turn: one narrator spawn the player never waits on.
    interjections: bool = True
    # This ~30k-token ceiling admits a 76-page adventure without swallowing the context.
    source_max_chars: int = Field(default=120_000, ge=1)
    # Also hard-coded in `.mcp.json` and `.codex/config.toml`; not `PORT`, set by too many shells.
    server_port: int = Field(default=8080, gt=0, lt=65536)
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")
    characters_dir: Path = Path("characters")

    @model_validator(mode="after")
    def _keys_present(self) -> Self:
        posting: list[tuple[str, ProviderName]] = [
            (what, feature.provider)
            for what, feature in (("media", self.media), ("speech", self.speech))
            if feature.enabled
        ]
        posting.extend((role, config.api) for role, config in self.roles.each() if config.api)
        for what, name in posting:
            if not self.providers.for_name(name).api_key:
                raise ValueError(f"{what} uses provider {name!r}, which has no api_key")
        return self


def read_settings() -> Settings:
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
