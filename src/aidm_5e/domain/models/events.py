from typing import Annotated, Literal

from pydantic import Field

from aidm.domain.base import PLAYER_ID, EntityId
from aidm.domain.events import CoreEvent

from ...content.records.base import ContentRef
from ...content.records.spells import SlotLevel, SpellLevel
from ...content.vocabulary import ConditionName, RestType
from ...utils.models import Ability, Frozen
from .progression import Advancement
from .stats import Wounds

RollKind = Literal["check", "save"]


class DcRolled(Frozen):
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
    wounds: Wounds

    @property
    def summary(self) -> str:
        if self.target_id == PLAYER_ID:
            return f"hp {self.delta:+d}"
        return f"{self.target_name} is {self.wounds}"


class ConditionChanged(Frozen):
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


class LevelUpAvailable(Frozen):
    type: Literal["level_up_available"] = "level_up_available"

    @property
    def summary(self) -> str:
        return "a level-up is available to the player"


class FeatureUsed(Frozen):
    type: Literal["feature_used"] = "feature_used"
    ref: ContentRef
    name: str
    spent: int = Field(ge=1)
    remaining: int = Field(ge=0)
    maximum: int = Field(ge=1)

    @property
    def summary(self) -> str:
        return f"used {self.name} ({self.remaining}/{self.maximum} uses remaining)"


class FeatureActivated(Frozen):
    type: Literal["feature_activated"] = "feature_activated"
    ref: ContentRef
    name: str

    @property
    def summary(self) -> str:
        return f"activated {self.name}"


class SpellCast(Frozen):
    type: Literal["spell_cast"] = "spell_cast"
    ref: ContentRef
    name: str
    slot_level: SpellLevel

    @property
    def summary(self) -> str:
        at = "" if self.slot_level == 0 else f" at level {self.slot_level}"
        return f"cast {self.name}{at}"


class SpellSlotSpent(Frozen):
    type: Literal["spell_slot_spent"] = "spell_slot_spent"
    slot_level: SlotLevel
    remaining: int = Field(ge=0)
    maximum: int = Field(ge=1)

    @property
    def summary(self) -> str:
        return (
            f"spent a level {self.slot_level} spell slot"
            f" ({self.remaining}/{self.maximum} remaining)"
        )


class PoolRefilled(Frozen):
    ref: ContentRef
    name: str
    maximum: int = Field(ge=1)


class SlotsRefilled(Frozen):
    slot_level: SlotLevel
    maximum: int = Field(ge=1)


class Rested(Frozen):
    type: Literal["rested"] = "rested"
    rest: RestType
    refilled: tuple[PoolRefilled, ...] = ()
    slots: tuple[SlotsRefilled, ...] = ()

    @property
    def summary(self) -> str:
        names = [pool.name for pool in self.refilled] + (["spell slots"] if self.slots else [])
        recharged = f"; recharged {', '.join(names)}" if names else ""
        return f"completed a {self.rest} rest{recharged}"


class LeveledUp(Frozen):
    type: Literal["leveled_up"] = "leveled_up"
    advancement: Advancement

    @property
    def summary(self) -> str:
        return f"reached level {self.advancement.progression.level}"


type Dnd5eRuleEvent = Annotated[
    DcRolled
    | AttackRolled
    | DiceRolled
    | HpChanged
    | ConditionChanged
    | LevelUpAvailable
    | FeatureUsed
    | FeatureActivated
    | SpellCast
    | SpellSlotSpent
    | Rested
    | LeveledUp,
    Field(discriminator="type"),
]

type Dnd5eEvent = CoreEvent | Dnd5eRuleEvent
