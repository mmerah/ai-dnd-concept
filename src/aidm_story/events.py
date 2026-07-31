from collections.abc import Mapping
from typing import Annotated, Literal, TypeGuard

from pydantic import Field, TypeAdapter

from aidm.domain.base import EngineId, EntityId
from aidm.domain.events import RuleEvent
from aidm.domain.json import FrozenJson
from aidm.utils.models import Frozen

from .models import StoryActorTag, StoryApproach, StoryCondition

StoryOutcome = Literal["strong", "mixed", "setback"]


class RiskRolled(Frozen):
    type: Literal["risk-rolled"] = "risk-rolled"
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
    def summary(self) -> str:
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


class StressChanged(Frozen):
    type: Literal["stress-changed"] = "stress-changed"
    actor_id: EntityId
    actor_name: str
    before: int
    after: int
    maximum: int

    @property
    def summary(self) -> str:
        return f"{self.actor_name} stress {self.before}->{self.after}/{self.maximum}"


class TakenOut(Frozen):
    type: Literal["taken-out"] = "taken-out"
    actor_id: EntityId
    actor_name: str

    @property
    def summary(self) -> str:
        return f"{self.actor_name} is taken out"


class Revived(Frozen):
    type: Literal["revived"] = "revived"
    actor_id: EntityId
    actor_name: str

    @property
    def summary(self) -> str:
        return f"{self.actor_name} is no longer taken out"


class ConditionApplied(Frozen):
    type: Literal["condition-applied"] = "condition-applied"
    actor_id: EntityId
    actor_name: str
    condition: StoryCondition

    @property
    def summary(self) -> str:
        return f"{self.actor_name} gains condition {self.condition.name}[id={self.condition.id}]"


class ConditionCleared(Frozen):
    type: Literal["condition-cleared"] = "condition-cleared"
    actor_id: EntityId
    actor_name: str
    condition: StoryCondition

    @property
    def summary(self) -> str:
        return f"{self.actor_name} loses condition {self.condition.name}[id={self.condition.id}]"


class GrowthMarked(Frozen):
    type: Literal["growth-marked"] = "growth-marked"
    before: int
    after: int

    @property
    def summary(self) -> str:
        return f"growth {self.before}->{self.after}/3"


class GrowthReset(Frozen):
    type: Literal["growth-reset"] = "growth-reset"
    before: Literal[3] = 3

    @property
    def summary(self) -> str:
        return f"growth reset from {self.before}/3"


class ApproachRaised(Frozen):
    type: Literal["approach-raised"] = "approach-raised"
    approach: StoryApproach
    before: int
    after: int

    @property
    def summary(self) -> str:
        return f"{self.approach} {self.before:+d}->{self.after:+d}"


class TagAdded(Frozen):
    type: Literal["tag-added"] = "tag-added"
    tag: StoryActorTag

    @property
    def summary(self) -> str:
        return f"tag added: {self.tag.name}[id={self.tag.id}, {self.tag.kind}]"


class TagRemoved(Frozen):
    type: Literal["tag-removed"] = "tag-removed"
    tag: StoryActorTag

    @property
    def summary(self) -> str:
        return f"tag removed: {self.tag.name}[id={self.tag.id}]"


class TagRewritten(Frozen):
    type: Literal["tag-rewritten"] = "tag-rewritten"
    before: StoryActorTag
    after: StoryActorTag

    @property
    def summary(self) -> str:
        return f"tag rewritten: {self.before.name}[id={self.before.id}] -> {self.after.name}"


class MaximumStressIncreased(Frozen):
    type: Literal["maximum-stress-increased"] = "maximum-stress-increased"
    before: int
    after: int

    @property
    def summary(self) -> str:
        return f"max stress {self.before}->{self.after}"


type StoryRuleEvent = Annotated[
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
    | MaximumStressIncreased,
    Field(discriminator="type"),
]
STORY_EVENT_ADAPTER: TypeAdapter[StoryRuleEvent] = TypeAdapter(StoryRuleEvent)


def encode_story_event(
    event: StoryRuleEvent, engine: EngineId, schema_version: int
) -> RuleEvent:
    payload = event.model_dump(mode="json", exclude={"type"})
    return RuleEvent(
        engine=engine,
        schema_version=schema_version,
        name=event.type,
        payload=payload,
    )


def _is_payload_mapping(
    value: FrozenJson,
) -> TypeGuard[Mapping[str, FrozenJson]]:
    return isinstance(value, Mapping)


def decode_story_event(
    event: RuleEvent,
    engine: EngineId,
    schema_version: int,
) -> StoryRuleEvent:
    if event.engine != engine:
        raise ValueError(f"Story event engine is {event.engine!r}, expected {engine!r}")
    if event.schema_version != schema_version:
        raise ValueError(f"Story event schema is {event.schema_version}, expected {schema_version}")
    if not _is_payload_mapping(event.payload):
        raise ValueError(f"Story event {event.name!r} payload must be an object")
    return STORY_EVENT_ADAPTER.validate_python({"type": event.name, **event.payload})
