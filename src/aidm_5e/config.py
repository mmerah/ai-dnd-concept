from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Dnd5eConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack_paths: tuple[Path, ...] | None = None
