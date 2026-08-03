from typing import Annotated, Literal

from pydantic import Field

from .base import PLAYER_ID, Entity, EntityId, Frozen


class FactBase(Frozen):
    @property
    def trace_summary(self) -> str:
        raise NotImplementedError

    @property
    def narrator_summary(self) -> str | None:
        return self.trace_summary


class CoreFactBase(FactBase):
    source: Literal["core"] = "core"


class EntityCreated(CoreFactBase):
    fact: Literal["entity_created"] = "entity_created"
    entity: Entity

    @property
    def trace_summary(self) -> str:
        return f"new {self.entity.kind}: {self.entity.name}"


class EntityDiscovered(CoreFactBase):
    fact: Literal["entity_discovered"] = "entity_discovered"
    entity_id: EntityId
    name: str

    @property
    def trace_summary(self) -> str:
        return f"learned of {self.name}"


class ActorMoved(CoreFactBase):
    fact: Literal["actor_moved"] = "actor_moved"
    actor_id: EntityId
    actor_name: str
    location_id: EntityId
    location_name: str

    @property
    def trace_summary(self) -> str:
        return f"{self.actor_name} moved to {self.location_name}"


type ItemDestination = Literal["actor", "location"]


class ItemMoved(CoreFactBase):
    fact: Literal["item_moved"] = "item_moved"
    item_id: EntityId
    item_name: str
    to_id: EntityId
    to_name: str
    to_kind: ItemDestination

    @property
    def trace_summary(self) -> str:
        if self.to_id == PLAYER_ID:
            return f"took {self.item_name}"
        if self.to_kind == "actor":
            return f"gave {self.item_name} to {self.to_name}"
        return f"left {self.item_name} at {self.to_name}"


type CoreFact = Annotated[
    EntityCreated | EntityDiscovered | ActorMoved | ItemMoved,
    Field(discriminator="fact"),
]
