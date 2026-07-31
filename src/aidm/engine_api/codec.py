from pydantic import BaseModel, TypeAdapter

from ..domain.base import Slug
from ..domain.engine import EngineData


class EngineCodec[ModelT: BaseModel]:
    def __init__(
        self,
        model: type[ModelT],
        *,
        engine: Slug,
        schema_version: int,
    ) -> None:
        self.adapter = TypeAdapter(model)
        self.engine = engine
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
