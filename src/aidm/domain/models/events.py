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


class ItemMoved(Frozen):
    """An item changes container. `to_kind` reads the destination for the Narrator's summary; the
    reducer removes the item from wherever it was and places it at `to_id`."""

    type: Literal["item_moved"] = "item_moved"
    item_id: EntityId
    item_name: str  # for the summary only; the ids drive state
    to_id: EntityId  # a location, an npc, or PLAYER_ID
    to_name: str
    to_kind: Literal["player", "npc", "location"]

    @property
    def summary(self) -> str:
        match self.to_kind:
            case "player":
                return f"took {self.item_name}"
            case "npc":
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
    delta: int

    @property
    def summary(self) -> str:
        return f"hp {self.delta:+d}"


class Moved(Frozen):
    """An actor (the player, as PLAYER_ID, or an NPC) changes location. Names ride along so the
    summary never leaks an id to the Narrator."""

    type: Literal["moved"] = "moved"
    subject_id: EntityId
    subject_name: str
    location_id: EntityId
    location_name: str

    @property
    def summary(self) -> str:
        return f"{self.subject_name} moved to {self.location_name}"


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
