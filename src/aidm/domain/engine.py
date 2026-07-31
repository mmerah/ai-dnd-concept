from collections.abc import Sequence
from typing import Self

from pydantic import Field, model_validator

from ..utils.models import Frozen
from .base import Slug
from .json import FrozenJson


class EngineRef(Frozen):
    id: Slug
    rules_version: int = Field(ge=1)


class DependencyStamp(Frozen):
    kind: Slug
    id: Slug
    version: str


class EngineStamp(Frozen):
    id: Slug
    rules_version: int = Field(ge=1)
    schema_version: int = Field(ge=1)
    dependencies: tuple[DependencyStamp, ...] = ()

    @model_validator(mode="after")
    def _normalized_dependencies(self) -> Self:
        keys = [(dependency.kind, dependency.id) for dependency in self.dependencies]
        if len(keys) != len(set(keys)):
            raise ValueError("engine dependencies contain duplicate kind/id pairs")
        if keys != sorted(keys):
            raise ValueError("engine dependencies must be sorted by kind and id")
        return self


class EngineData(Frozen):
    engine: Slug
    schema_version: int = Field(ge=1)
    payload: FrozenJson


def dependency_stamps(stamps: Sequence[DependencyStamp]) -> tuple[DependencyStamp, ...]:
    return tuple(sorted(stamps, key=lambda stamp: (stamp.kind, stamp.id)))


def require_envelope(data: EngineData, stamp: EngineStamp, purpose: str) -> None:
    if data.engine != stamp.id:
        raise ValueError(f"{purpose} engine is {data.engine!r}, selected engine is {stamp.id!r}")
    if data.schema_version != stamp.schema_version:
        raise ValueError(
            f"{purpose} schema_version is {data.schema_version}, "
            f"selected engine schema_version is {stamp.schema_version}"
        )
