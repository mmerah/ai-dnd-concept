from pydantic import Field

from ..utils.models import Frozen
from .base import EntityId, Slug
from .engine import EngineStamp
from .json import FrozenJson


class DirectionBase(Frozen):
    intent: str
    tone: str
    speaker_id: EntityId | None = None


class DirectionRecord(Frozen):
    engine: Slug
    schema_version: int = Field(ge=1)
    intent: str
    tone: str
    speaker_id: EntityId | None
    mechanics: FrozenJson


def require_direction(record: DirectionRecord, stamp: EngineStamp) -> None:
    if record.engine != stamp.id:
        raise ValueError(
            f"direction record engine is {record.engine!r}, selected engine is {stamp.id!r}"
        )
    if record.schema_version != stamp.schema_version:
        raise ValueError(
            f"direction record schema_version is {record.schema_version}, "
            f"selected engine schema_version is {stamp.schema_version}"
        )
