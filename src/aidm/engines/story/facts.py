from typing import Annotated, Literal

from pydantic import Field

from aidm.base import EntityId
from aidm.facts import CoreFact, FactBase

from .state import StoryActorTag, StoryApproach, StoryCondition, StoryGearTag

StoryOutcome = Literal["strong", "mixed", "setback"]


class StoryFactBase(FactBase):
    source: Literal["story"] = "story"


class RiskRolled(StoryFactBase):
    fact: Literal["risk-rolled"] = "risk-rolled"
    actor_id: EntityId
    actor_name: str
    dice: tuple[int, int]
    approach: StoryApproach
    approach_modifier: int
    helpful_modifier: int
    hindering_modifier: int
    difficulty: int
    total: int
    outcome: StoryOutcome

    @property
    def trace_summary(self) -> str:
        modifiers = (
            self.approach_modifier
            + self.helpful_modifier
            + self.hindering_modifier
            - self.difficulty
        )
        return (
            f"{self.actor_name} risk: {self.dice[0]}+{self.dice[1]} {modifiers:+d}"
            f" = {self.total}: {self.outcome}"
        )

    @property
    def narrator_summary(self) -> str:
        return f"{self.actor_name}'s attempt ends in a {self.outcome}"


class StressChanged(StoryFactBase):
    fact: Literal["stress-changed"] = "stress-changed"
    actor_id: EntityId
    actor_name: str
    before: int
    after: int
    maximum: int

    @property
    def trace_summary(self) -> str:
        return f"{self.actor_name} stress {self.before}->{self.after}/{self.maximum}"

    @property
    def narrator_summary(self) -> str:
        if self.after < self.before:
            return f"{self.actor_name} recovers some composure"
        return f"{self.actor_name} comes under more pressure"


class TakenOut(StoryFactBase):
    fact: Literal["taken-out"] = "taken-out"
    actor_id: EntityId
    actor_name: str

    @property
    def trace_summary(self) -> str:
        return f"{self.actor_name} is taken out"


class Revived(StoryFactBase):
    fact: Literal["revived"] = "revived"
    actor_id: EntityId
    actor_name: str

    @property
    def trace_summary(self) -> str:
        return f"{self.actor_name} is no longer taken out"


class ConditionApplied(StoryFactBase):
    fact: Literal["condition-applied"] = "condition-applied"
    actor_id: EntityId
    actor_name: str
    condition: StoryCondition

    @property
    def trace_summary(self) -> str:
        return f"{self.actor_name} gains condition {self.condition.name}[id={self.condition.id}]"

    @property
    def narrator_summary(self) -> str:
        return f"{self.actor_name} is now {self.condition.name}"


class ConditionCleared(StoryFactBase):
    fact: Literal["condition-cleared"] = "condition-cleared"
    actor_id: EntityId
    actor_name: str
    condition: StoryCondition

    @property
    def trace_summary(self) -> str:
        return f"{self.actor_name} loses condition {self.condition.name}[id={self.condition.id}]"

    @property
    def narrator_summary(self) -> str:
        return f"{self.actor_name} is no longer {self.condition.name}"


class GrowthMarked(StoryFactBase):
    fact: Literal["growth-marked"] = "growth-marked"
    before: int
    after: int

    @property
    def trace_summary(self) -> str:
        return f"growth {self.before}->{self.after}/3"

    @property
    def narrator_summary(self) -> None:
        return None


class GrowthReset(StoryFactBase):
    fact: Literal["growth-reset"] = "growth-reset"
    before: Literal[3] = 3

    @property
    def trace_summary(self) -> str:
        return f"growth reset from {self.before}/3"

    @property
    def narrator_summary(self) -> None:
        return None


class ApproachRaised(StoryFactBase):
    fact: Literal["approach-raised"] = "approach-raised"
    approach: StoryApproach
    before: int
    after: int

    @property
    def trace_summary(self) -> str:
        return f"{self.approach} {self.before:+d}->{self.after:+d}"

    @property
    def narrator_summary(self) -> str:
        return f"the player's {self.approach} approach improves"


class TagAdded(StoryFactBase):
    fact: Literal["tag-added"] = "tag-added"
    tag: StoryActorTag

    @property
    def trace_summary(self) -> str:
        return f"tag added: {self.tag.name}[id={self.tag.id}, {self.tag.kind}]"

    @property
    def narrator_summary(self) -> str:
        return f"the player gains {self.tag.name}"


class TagRemoved(StoryFactBase):
    fact: Literal["tag-removed"] = "tag-removed"
    tag: StoryActorTag

    @property
    def trace_summary(self) -> str:
        return f"tag removed: {self.tag.name}[id={self.tag.id}]"

    @property
    def narrator_summary(self) -> str:
        return f"the player leaves {self.tag.name} behind"


class TagRewritten(StoryFactBase):
    fact: Literal["tag-rewritten"] = "tag-rewritten"
    before: StoryActorTag
    after: StoryActorTag

    @property
    def trace_summary(self) -> str:
        return f"tag rewritten: {self.before.name}[id={self.before.id}] -> {self.after.name}"

    @property
    def narrator_summary(self) -> str:
        return f"the player's burden becomes {self.after.name}"


class GearAcquired(StoryFactBase):
    fact: Literal["gear-acquired"] = "gear-acquired"
    item_id: EntityId
    item_name: str
    gear: StoryGearTag

    @property
    def trace_summary(self) -> str:
        return f"gear acquired: {self.item_name} ({self.gear.name})"

    @property
    def narrator_summary(self) -> str:
        return f"the player now carries {self.item_name}"


class MaximumStressIncreased(StoryFactBase):
    fact: Literal["maximum-stress-increased"] = "maximum-stress-increased"
    before: int
    after: int

    @property
    def trace_summary(self) -> str:
        return f"max stress {self.before}->{self.after}"

    @property
    def narrator_summary(self) -> str:
        return "the player becomes more resilient"


type StoryFact = Annotated[
    RiskRolled
    | StressChanged
    | TakenOut
    | Revived
    | ConditionApplied
    | ConditionCleared
    | GrowthMarked
    | GrowthReset
    | ApproachRaised
    | TagAdded
    | TagRemoved
    | TagRewritten
    | GearAcquired
    | MaximumStressIncreased,
    Field(discriminator="fact"),
]

type Emitted = CoreFact | StoryFact
