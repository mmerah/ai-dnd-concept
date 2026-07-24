"""Typed events: the only data the single pure reducer consumes to produce new state."""

from typing import Annotated, Literal

from pydantic import Field

from .base import Ability, EntityId, Frozen
from .entities import Entity


class CheckRolled(Frozen):
    type: Literal["check_rolled"] = "check_rolled"
    ability: Ability
    dc: int
    roll: int
    total: int
    success: bool

    @property
    def summary(self) -> str:
        verdict = "SUCCESS" if self.success else "FAILURE"
        return f"{self.ability} check: {self.roll} -> {self.total} vs DC {self.dc}: {verdict}"


class InventoryChanged(Frozen):
    type: Literal["inventory_changed"] = "inventory_changed"
    item: str
    delta: Literal[1, -1]

    @property
    def summary(self) -> str:
        return f"{'gained' if self.delta > 0 else 'lost'} item: {self.item}"


class HpChanged(Frozen):
    type: Literal["hp_changed"] = "hp_changed"
    delta: int

    @property
    def summary(self) -> str:
        return f"hp {self.delta:+d}"


class Moved(Frozen):
    type: Literal["moved"] = "moved"
    entity_id: EntityId
    name: str  # carried so the summary never leaks an id to the Narrator

    @property
    def summary(self) -> str:
        return f"moved to {self.name}"


class EntityDiscovered(Frozen):
    type: Literal["entity_discovered"] = "entity_discovered"
    entity_id: EntityId
    name: str

    @property
    def summary(self) -> str:
        return f"learned of {self.name}"


class EntityCreated(Frozen):
    type: Literal["entity_created"] = "entity_created"
    entity: Entity

    @property
    def summary(self) -> str:
        return f"new {self.entity.kind}: {self.entity.name}"


Event = Annotated[
    CheckRolled | InventoryChanged | HpChanged | Moved | EntityDiscovered | EntityCreated,
    Field(discriminator="type"),
]
