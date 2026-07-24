"""Canon entities, the requests to grow them, and the lookups over the live entity map."""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field

from .base import EntityId, Frozen, Kind


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


class NpcEntity(BaseEntity):
    kind: Literal["npc"] = "npc"
    location_id: EntityId  # the location the NPC stands in
    inventory: list[EntityId] = Field(default_factory=list)  # canon items the NPC carries


class LocationEntity(BaseEntity):
    kind: Literal["location"] = "location"


class ItemEntity(BaseEntity):
    kind: Literal["item"] = "item"
    # Where the item lies, or None while an actor carries it (then it is in exactly one inventory).
    # GameState enforces this held-xor-located invariant.
    location_id: EntityId | None = None


# A `kind`-discriminated union: each kind owns its fields instead of a bag of optionals on one
# class. `Entity` is a type alias, not constructible — build via a concrete class or `make_entity`.
Entity = Annotated[NpcEntity | LocationEntity | ItemEntity, Field(discriminator="kind")]


def make_entity(
    kind: Kind,
    *,
    id: EntityId,
    name: str,
    brief: str,
    location_id: EntityId | None = None,
    detail: EntityDetail | None = None,
    known: bool = False,
    authored: bool = True,
) -> Entity:
    """Construct the concrete entity for a kind known only at runtime (Creator, improvised items).
    Exhaustive on `Kind`, so a new kind is a type error here, not a silent gap. An NPC must be given
    a location; an item's `location_id` is None when it is created straight into an inventory."""
    match kind:
        case "npc":
            if location_id is None:
                raise ValueError("an npc must be created in a location")
            return NpcEntity(
                id=id, name=name, brief=brief, location_id=location_id,
                detail=detail, known=known, authored=authored,
            )
        case "location":
            return LocationEntity(
                id=id, name=name, brief=brief, detail=detail, known=known, authored=authored
            )
        case "item":
            return ItemEntity(
                id=id, name=name, brief=brief, location_id=location_id,
                detail=detail, known=known, authored=authored,
            )


class GrowthRequest(Frozen):
    kind: Kind
    name: str
    brief: str
    # The name of the location an npc/item belongs in — an existing one, or a location requested in
    # the same batch (created first). None places it where the player is. Ignored for a location.
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
