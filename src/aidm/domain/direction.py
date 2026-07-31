from pydantic import Field

from ..utils.models import Frozen
from .base import EngineId, EntityId
from .json import FrozenJson


class DirectionRecord(Frozen):
    engine: EngineId
    schema_version: int = Field(ge=1)
    intent: str
    tone: str
    speaker_id: EntityId | None
    mechanics: FrozenJson
