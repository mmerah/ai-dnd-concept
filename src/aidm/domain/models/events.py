"""Typed events: the only data the single pure reducer consumes to produce new state."""

from typing import Annotated, Literal

from pydantic import Field

from .base import PLAYER_ID, Ability, EntityId, Frozen
from .entities import Entity
from .stats import Condition


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


ItemDestination = Literal["actor", "location"]


class ItemMoved(Frozen):
    """An item changes container. `to_kind` shapes the sentence only; the reducer reads the
    destination's own type, so the two can never disagree."""

    type: Literal["item_moved"] = "item_moved"
    item_id: EntityId
    item_name: str  # for the summary only; the ids drive state
    to_id: EntityId
    to_name: str
    to_kind: ItemDestination

    @property
    def summary(self) -> str:
        if self.to_id == PLAYER_ID:
            return f"took {self.item_name}"
        match self.to_kind:
            case "actor":
                return f"gave {self.item_name} to {self.to_name}"
            case "location":
                return f"left {self.item_name} at {self.to_name}"


class DiceRolled(Frozen):
    type: Literal["dice_rolled"] = "dice_rolled"
    dice: str
    total: int

    @property
    def summary(self) -> str:
        return f"rolled {self.dice}: {self.total}"


class HpChanged(Frozen):
    type: Literal["hp_changed"] = "hp_changed"
    target_id: EntityId
    target_name: str
    delta: int
    condition: Condition  # the target's condition after the change

    @property
    def summary(self) -> str:
        if self.target_id == PLAYER_ID:
            return f"hp {self.delta:+d}"
        return f"{self.target_name} is {self.condition}"


class Moved(Frozen):
    """Names ride along so the summary never leaks an id."""

    type: Literal["moved"] = "moved"
    actor_id: EntityId
    actor_name: str
    location_id: EntityId
    location_name: str

    @property
    def summary(self) -> str:
        return f"{self.actor_name} moved to {self.location_name}"


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
    CheckRolled
    | DiceRolled
    | ItemMoved
    | HpChanged
    | Moved
    | EntityDiscovered
    | EntityCreated,
    Field(discriminator="type"),
]
