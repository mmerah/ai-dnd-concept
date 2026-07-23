"""Runtime configuration, loaded once from .env. Paths are relative to the working directory."""

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ai_api_key: str
    ai_model: str = "openai/gpt-oss-120b"
    ai_base_url: str = "https://openrouter.ai/api/v1"
    max_growth: int = 3
    history_window: int = 6
    saves_dir: Path = Path("saves")
    scenarios_dir: Path = Path("scenarios")


@cache
def settings() -> Settings:
    return Settings.model_validate({})
