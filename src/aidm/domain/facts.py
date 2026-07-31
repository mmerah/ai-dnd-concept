from typing import Annotated, Literal

from pydantic import Field

from ..utils.models import Frozen
from .base import PLAYER_ID, EntityId
from .entities import Entity


class CoreFactBase(Frozen):
    source: Literal["core"] = "core"


class EntityCreated(CoreFactBase):
    fact: Literal["entity_created"] = "entity_created"
    entity: Entity


class EntityDiscovered(CoreFactBase):
    fact: Literal["entity_discovered"] = "entity_discovered"
    entity_id: EntityId
    name: str


class ActorMoved(CoreFactBase):
    fact: Literal["actor_moved"] = "actor_moved"
    actor_id: EntityId
    actor_name: str
    location_id: EntityId
    location_name: str


type ItemDestination = Literal["actor", "location"]


class ItemMoved(CoreFactBase):
    fact: Literal["item_moved"] = "item_moved"
    item_id: EntityId
    item_name: str
    to_id: EntityId
    to_name: str
    to_kind: ItemDestination


type CoreFact = Annotated[
    EntityCreated | EntityDiscovered | ActorMoved | ItemMoved,
    Field(discriminator="fact"),
]


def core_fact_summary(fact: CoreFact) -> str:
    """Core facts carry no private canon, so the trace and the Narrator read the same line."""
    match fact:
        case EntityCreated(entity=entity):
            return f"new {entity.kind}: {entity.name}"
        case EntityDiscovered(name=name):
            return f"learned of {name}"
        case ActorMoved(actor_name=actor, location_name=location):
            return f"{actor} moved to {location}"
        case ItemMoved(item_name=item, to_id=to_id) if to_id == PLAYER_ID:
            return f"took {item}"
        case ItemMoved(item_name=item, to_kind="actor", to_name=actor):
            return f"gave {item} to {actor}"
        case ItemMoved(item_name=item, to_name=location):
            return f"left {item} at {location}"
