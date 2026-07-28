"""Canon entities and the requests to grow them."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from ...content import ContentRef
from ...utils.models import Frozen
from .base import EntityId, Kind
from .progression import Progression
from .stats import StatBlock


class EntityDetail(Frozen):
    """What a Creator adds on top of a growth request."""

    description: str
    hook: str


class BaseEntity(Frozen):
    id: EntityId
    name: str
    brief: str
    # The archetype this instance came from; `engine/bestiary.py` owns what that means.
    ref: ContentRef | None = None
    detail: EntityDetail | None = None
    known: bool = False  # revealed to the player
    authored: bool = True  # False once a Creator invented it mid-play


class ActorEntity(BaseEntity):
    """An actor, the player included."""

    kind: Literal["actor"] = "actor"
    location_id: EntityId  # the location the actor stands in
    # A factory, not a shared instance: pydantic deep-copies a model default, and a `FrozenMap`
    # field inside it holds a `mappingproxy`, which cannot be copied.
    stats: StatBlock = Field(default_factory=StatBlock)
    # The player's alone (`GameState` enforces it): no SRD monster has class levels, and building
    # symmetric progression for NPCs statted by challenge rating would be a speculative abstraction.
    progression: Progression | None = None


class LocationEntity(BaseEntity):
    kind: Literal["location"] = "location"


class ItemEntity(BaseEntity):
    kind: Literal["item"] = "item"
    # The location it lies at, or the actor carrying it. Always set: an item is somewhere.
    # `GameState` enforces this names a location or an actor and never another item, which is what
    # keeps containment one level deep and acyclic by construction.
    container_id: EntityId


# A `kind`-discriminated union: each kind owns its fields instead of a bag of optionals on one
# class. `Entity` is a type alias, not constructible — instantiate a concrete class, or validate a
# payload through the adapter when the kind is only known at runtime (the Creator).
Entity = Annotated[ActorEntity | LocationEntity | ItemEntity, Field(discriminator="kind")]

# The discriminator picks the class and `extra="forbid"` polices the fields, so "an actor must be
# created in a location" is a ValidationError with no dispatch of our own.
ENTITY_ADAPTER: TypeAdapter[Entity] = TypeAdapter(Entity)


def placement(kind: Kind, location_id: EntityId) -> dict[str, EntityId]:
    """Where a new entity of this kind stands, as adapter input. Which field names its place is
    entity shape — an item names its container, an actor its location — so it is answered here
    rather than wherever an entity happens to be built."""
    match kind:
        case "location":
            return {}
        case "actor":
            return {"location_id": location_id}
        case "item":
            return {"container_id": location_id}


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
