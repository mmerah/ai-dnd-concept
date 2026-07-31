from pydantic import BaseModel, Field, TypeAdapter

from ..utils.models import EMPTY_FROZEN_MAP, Frozen, FrozenMap
from .base import EngineId, EntityId
from .json import FrozenJson


class EngineData(Frozen):
    engine: EngineId
    schema_version: int = Field(ge=1)
    payload: FrozenJson


class EngineInitialization(Frozen):
    game_rules: EngineData
    entity_rules: FrozenMap[EntityId, EngineData | None] = EMPTY_FROZEN_MAP


class AdvancementStatus(Frozen):
    headline: str
    detail: tuple[str, ...] = ()
    progress: float = Field(default=0.0, ge=0.0, le=1.0)


def require_engine(data: EngineData, engine: EngineId, purpose: str) -> None:
    if data.engine != engine:
        raise ValueError(f"{purpose} engine is {data.engine!r}, selected engine is {engine!r}")


class EngineCodec[ModelT: BaseModel]:
    def __init__(self, model: type[ModelT], *, engine: EngineId, schema_version: int) -> None:
        self.adapter = TypeAdapter(model)
        self.engine: EngineId = engine
        self.schema_version = schema_version

    def decode(self, data: EngineData) -> ModelT:
        if data.engine != self.engine:
            raise ValueError(
                f"engine payload is for {data.engine!r}, codec expects {self.engine!r}"
            )
        if data.schema_version != self.schema_version:
            raise ValueError(
                f"engine payload schema is {data.schema_version}, "
                f"codec expects {self.schema_version}"
            )
        return self.adapter.validate_python(data.payload)

    def encode(self, value: ModelT) -> EngineData:
        validated = self.adapter.validate_python(value)
        return EngineData(
            engine=self.engine,
            schema_version=self.schema_version,
            payload=validated.model_dump(mode="json"),
        )
