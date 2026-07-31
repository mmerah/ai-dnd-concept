from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    WrapSerializer,
)


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def __hash__(self) -> int:
        raise TypeError(f"unhashable type: {type(self).__name__!r}")


def _immutable[K, V](mapping: Mapping[K, V]) -> Mapping[K, V]:
    return MappingProxyType(dict(mapping))


def _as_dict[K, V](mapping: Mapping[K, V], serialize: SerializerFunctionWrapHandler) -> object:
    return serialize(dict(mapping))


type FrozenMap[K, V] = Annotated[
    Mapping[K, V],
    AfterValidator(_immutable),
    WrapSerializer(_as_dict),
]

EMPTY_FROZEN_MAP = Field(default_factory=dict, validate_default=True)


def updated[T: BaseModel](obj: T, **changes: object) -> T:
    return type(obj).model_validate(obj.model_dump(round_trip=True) | changes)
