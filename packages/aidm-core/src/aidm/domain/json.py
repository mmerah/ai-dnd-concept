import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, TypeGuard

from pydantic import AfterValidator, BeforeValidator, PlainSerializer

type JsonScalar = str | int | float | bool | None


def _is_sequence(value: object) -> TypeGuard[list[object] | tuple[object, ...]]:
    return isinstance(value, list | tuple)


def _is_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    return isinstance(value, tuple)


def _is_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    return isinstance(value, Mapping)


def _require_json(value: object) -> object:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if _is_sequence(value):
        return value
    if _is_mapping(value):
        for key in value:
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
        return value
    raise ValueError(f"{type(value).__name__} is not a JSON value")


def _freeze_json(value: object) -> object:
    if _is_mapping(value):
        return MappingProxyType(dict(value))
    if _is_sequence(value):
        return tuple(value)
    return value


def thaw_json(value: object) -> object:
    if _is_mapping(value):
        thawed: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            thawed[key] = thaw_json(item)
        return thawed
    if _is_tuple(value):
        return [thaw_json(item) for item in value]
    return value


type FrozenJson = Annotated[
    JsonScalar | tuple["FrozenJson", ...] | Mapping[str, "FrozenJson"],
    BeforeValidator(_require_json),
    AfterValidator(_freeze_json),
    PlainSerializer(thaw_json),
]
