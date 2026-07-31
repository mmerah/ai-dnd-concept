from typing import Annotated, Literal

from pydantic import Field

from ..utils.models import Frozen
from .base import EngineId, EntityId, Slug
from .entities import Entity
from .json import FrozenJson


class EntityCreated(Frozen):
    type: Literal["entity_created"] = "entity_created"
    entity: Entity


class EntityDiscovered(Frozen):
    type: Literal["entity_discovered"] = "entity_discovered"
    entity_id: EntityId
    name: str


class ActorMoved(Frozen):
    type: Literal["actor_moved"] = "actor_moved"
    actor_id: EntityId
    actor_name: str
    location_id: EntityId
    location_name: str


type ItemDestination = Literal["actor", "location"]


class ItemMoved(Frozen):
    type: Literal["item_moved"] = "item_moved"
    item_id: EntityId
    item_name: str
    to_id: EntityId
    to_name: str
    to_kind: ItemDestination


type CoreEvent = Annotated[
    EntityCreated | EntityDiscovered | ActorMoved | ItemMoved,
    Field(discriminator="type"),
]


class RuleEvent(Frozen):
    type: Literal["rule_event"] = "rule_event"
    engine: EngineId
    schema_version: int = Field(ge=1)
    name: Slug
    payload: FrozenJson


type Event = CoreEvent | RuleEvent
