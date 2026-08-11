import re
from collections.abc import Iterable
from typing import Annotated, Literal, NewType

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    """A value nothing owns: a fact, a direction, or an authored record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def __hash__(self) -> int:
        raise TypeError(f"unhashable type: {type(self).__name__!r}")


class Mutable(BaseModel):
    """State a resolution mutates in place; commit revalidates the whole draft once."""

    model_config = ConfigDict(extra="forbid")


Kind = Literal["actor", "location", "item"]
ThreadStatus = Literal["active", "resolved", "dormant"]
EngineId = NewType("EngineId", str)
EntityId = NewType("EntityId", str)
RelationId = NewType("RelationId", str)
SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
Slug = Annotated[str, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=64)]

PLAYER_ID = EntityId("player")
SAVE_VERSION = 47


def content_id(value: str) -> Slug:
    """Narrow a routed id before it names a directory, so `Slug` downstream is a fact."""
    if re.fullmatch(SLUG_PATTERN, value) is None:
        raise ValueError(f"invalid content id {value!r}")
    return value


def slug(name: str, taken: Iterable[EntityId]) -> EntityId:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "entity"
    used = set(taken)
    candidate, number = EntityId(base), 2
    while candidate in used:
        candidate, number = EntityId(f"{base}_{number}"), number + 1
    return candidate


class EntityDetail(Frozen):
    description: str
    hook: str


class Entity(Mutable):
    id: EntityId
    kind: Kind
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False
    # Which kinds may hold which is one rule, in `world.check_placement`.
    parent_id: EntityId | None = None
