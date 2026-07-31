from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Dnd5eConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="AIDM_DND5E_",
    )

    pack_paths: tuple[Path, ...] | None = None
