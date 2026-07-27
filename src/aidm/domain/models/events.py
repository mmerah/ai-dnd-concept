"""Typed events: the only data the single pure reducer consumes to produce new state."""

from typing import Annotated, Literal

from pydantic import Field

from ...content.vocabulary import ConditionName
from ...utils.models import Ability, Frozen
from .base import PLAYER_ID, EntityId
from .entities import Entity
from .progression import Advancement
from .stats import Wounds

# A check is attempted, a save resists something aimed at you. The numbers are the same shape; which
# bonus applies is not, so the roll says which it was.
RollKind = Literal["check", "save"]


class DcRolled(Frozen):
    """What `DcRoll` resolves to, named for the base rather than for the check: a save is not a
    check, and `kind` is the only thing separating them."""

    type: Literal["dc_rolled"] = "dc_rolled"
    actor_id: EntityId
    actor_name: str
    kind: RollKind
    ability: Ability
    dc: int
    roll: int
    total: int
    success: bool

    @property
    def summary(self) -> str:
        who = "" if self.actor_id == PLAYER_ID else f"{self.actor_name} "
        verdict = "SUCCESS" if self.success else "FAILURE"
        return (
            f"{who}{self.ability} {self.kind}: {self.roll} -> {self.total}"
            f" vs DC {self.dc}: {verdict}"
        )


class AttackRolled(Frozen):
    """A to-hit against a target's armour class. The Narrator is shown the AC for the same reason it
    is shown a DC: it must not narrate a blow that missed."""

    type: Literal["attack_rolled"] = "attack_rolled"
    actor_name: str
    target_name: str
    weapon: str
    roll: int
    total: int
    ac: int
    hit: bool

    @property
    def summary(self) -> str:
        outcome = "HIT" if self.hit else "MISS"
        return (
            f"{self.actor_name} attacks {self.target_name} with {self.weapon}:"
            f" {self.roll} -> {self.total} vs ac {self.ac}: {outcome}"
        )


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
    wounds: Wounds  # how the target reads after the change

    @property
    def summary(self) -> str:
        if self.target_id == PLAYER_ID:
            return f"hp {self.delta:+d}"
        return f"{self.target_name} is {self.wounds}"


class ConditionChanged(Frozen):
    """An SRD condition taking hold or lifting. Immunity is resolved before this is emitted, so the
    event is only ever the change that happened."""

    type: Literal["condition_changed"] = "condition_changed"
    target_id: EntityId
    target_name: str
    condition: ConditionName
    active: bool

    @property
    def summary(self) -> str:
        who = "the player" if self.target_id == PLAYER_ID else self.target_name
        held = "is" if self.active else "is no longer"
        return f"{who} {held} {self.condition}"


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


class LeveledUp(Frozen):
    """The player advanced. It names no target: progression is the player's alone, so an event that
    could name someone else would contradict the invariant that says so."""

    type: Literal["leveled_up"] = "leveled_up"
    advancement: Advancement

    @property
    def summary(self) -> str:
        return f"reached level {self.advancement.progression.level}"


Event = Annotated[
    DcRolled
    | AttackRolled
    | DiceRolled
    | ItemMoved
    | HpChanged
    | ConditionChanged
    | Moved
    | EntityDiscovered
    | EntityCreated
    | LeveledUp,
    Field(discriminator="type"),
]
