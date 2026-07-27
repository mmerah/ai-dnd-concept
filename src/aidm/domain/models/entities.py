"""Canon entities, the requests to grow them, and the lookups over the live entity map."""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from .base import EntityId, Frozen, Kind
from .stats import StatBlock


class EntityDetail(Frozen):
    """What a Creator adds on top of a growth request."""

    description: str
    hook: str


class BaseEntity(Frozen):
    id: EntityId
    name: str
    brief: str
    detail: EntityDetail | None = None
    known: bool = False  # revealed to the player
    authored: bool = True  # False once a Creator invented it mid-play


class ActorEntity(BaseEntity):
    """An actor, the player included."""

    kind: Literal["actor"] = "actor"
    location_id: EntityId  # the location the actor stands in
    inventory: list[EntityId] = Field(default_factory=list)  # canon items the actor carries
    stats: StatBlock = StatBlock()


class LocationEntity(BaseEntity):
    kind: Literal["location"] = "location"


class ItemEntity(BaseEntity):
    kind: Literal["item"] = "item"
    # Where the item lies, or None while an actor carries it (then it is in exactly one inventory).
    # GameState enforces this held-xor-located invariant.
    location_id: EntityId | None = None


# A `kind`-discriminated union: each kind owns its fields instead of a bag of optionals on one
# class. `Entity` is a type alias, not constructible — instantiate a concrete class, or validate a
# payload through the adapter when the kind is only known at runtime (the Creator).
Entity = Annotated[ActorEntity | LocationEntity | ItemEntity, Field(discriminator="kind")]

# The discriminator picks the class and `extra="forbid"` polices the fields, so "an actor must be
# created in a location" is a ValidationError with no dispatch of our own.
ENTITY_ADAPTER: TypeAdapter[Entity] = TypeAdapter(Entity)


def placement(kind: Kind, location_id: EntityId) -> dict[str, EntityId]:
    """Where a new entity of this kind stands, as adapter input. Which kinds carry a location is
    entity shape, so it is answered here rather than wherever an entity happens to be built."""
    return {} if kind == "location" else {"location_id": location_id}


class GrowthRequest(Frozen):
    kind: Kind
    name: str
    brief: str
    # The name of the location an actor/item belongs in — an existing one, or a location requested
    # in the same batch (created first). None places it where the player is. Ignored for a location.
    location: str | None = None


class Growth(Frozen):
    requests: list[GrowthRequest] = Field(default_factory=list)


# `duplicate_name`: a name that already exists; `over_cap`: admissible but beyond the turn's budget.
GrowthRejectionReason = Literal["duplicate_name", "over_cap"]


class RejectedGrowth(Frozen):
    """A growth request screening refused, with why — kept so the trace shows every drop."""

    request: GrowthRequest
    reason: GrowthRejectionReason


def find(entities: Mapping[EntityId, Entity], entity_id: EntityId) -> Entity | None:
    return entities.get(entity_id)
