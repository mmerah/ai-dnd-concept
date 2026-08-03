import re
from collections.abc import Iterable
from typing import Annotated, Literal, NewType, get_args

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    """A value nothing owns: a fact, a direction, or an authored record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def __hash__(self) -> int:
        raise TypeError(f"unhashable type: {type(self).__name__!r}")


class Mutable(BaseModel):
    """State a resolution mutates in place; commit revalidates the whole draft once."""

    model_config = ConfigDict(extra="forbid")


Role = Literal["director", "narrator", "maintainer", "creator"]
EngineId = Literal["story", "dnd5e"]
Kind = Literal["actor", "location", "item"]
EntityId = NewType("EntityId", str)
SLUG_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
Slug = Annotated[str, Field(pattern=rf"^{SLUG_PATTERN}$", max_length=64)]

PLAYER_ID = EntityId("player")
ROLES: tuple[Role, ...] = get_args(Role)
ENGINE_IDS: tuple[EngineId, ...] = get_args(EngineId)
SAVE_VERSION = 20


def as_engine_id(value: str) -> EngineId:
    """Narrow a routed string; an unknown engine is a bug, not a choice."""
    for engine in ENGINE_IDS:
        if engine == value:
            return engine
    raise ValueError(f"unknown engine {value!r}")


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


class AdvancementDecision(Frozen):
    """What the player chose in an engine's advancement UI; the engine that minted it applies it."""


class EntityDetail(Frozen):
    description: str
    hook: str


class BaseEntity(Mutable):
    id: EntityId
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False


class ActorEntity(BaseEntity):
    kind: Literal["actor"] = "actor"
    location_id: EntityId


class ItemEntity(BaseEntity):
    kind: Literal["item"] = "item"
    container_id: EntityId


class LocationEntity(BaseEntity):
    kind: Literal["location"] = "location"


type Entity = Annotated[ActorEntity | ItemEntity | LocationEntity, Field(discriminator="kind")]


def placement(kind: Kind, location_id: EntityId) -> dict[str, EntityId]:
    match kind:
        case "location":
            return {}
        case "actor":
            return {"location_id": location_id}
        case "item":
            return {"container_id": location_id}
