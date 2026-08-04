from typing import Literal, Self

from pydantic import Field, model_validator

from aidm.core.base import PLAYER_ID, EntityId, Frozen, Mutable, Slug
from aidm.core.content import Rules
from aidm.core.world import GameState

StoryApproach = Literal["bold", "subtle", "clever", "empathetic"]
APPROACH_NAMES: tuple[StoryApproach, ...] = ("bold", "subtle", "clever", "empathetic")
MIN_APPROACH = -1
MAX_APPROACH = 3
MIN_MAX_STRESS = 3
MAX_MAX_STRESS = 7
GROWTH_REQUIRED = 3


class StoryApproaches(Frozen):
    bold: int = Field(ge=MIN_APPROACH, le=MAX_APPROACH)
    subtle: int = Field(ge=MIN_APPROACH, le=MAX_APPROACH)
    clever: int = Field(ge=MIN_APPROACH, le=MAX_APPROACH)
    empathetic: int = Field(ge=MIN_APPROACH, le=MAX_APPROACH)

    def score(self, approach: StoryApproach) -> int:
        match approach:
            case "bold":
                return self.bold
            case "subtle":
                return self.subtle
            case "clever":
                return self.clever
            case "empathetic":
                return self.empathetic


class StoryActorTag(Frozen):
    id: Slug
    name: str
    kind: Literal["edge", "burden", "bond"]
    description: str


def _unique_tag_ids(tags: tuple[StoryActorTag, ...]) -> None:
    tag_ids = [tag.id for tag in tags]
    if len(tag_ids) != len(set(tag_ids)):
        raise ValueError("Story actor tag ids must be unique")


class StoryCondition(Frozen):
    id: Slug = Field(description="Stable slug id for this injury or status.")
    name: str = Field(description="Short fictional name for the injury or status.")
    description: str = Field(description="The concrete constraint this puts on the actor.")


class StoryActorState(Mutable):
    approaches: StoryApproaches
    tags: tuple[StoryActorTag, ...] = ()
    stress: int = Field(default=0, ge=0)
    max_stress: int = Field(default=5, ge=MIN_MAX_STRESS, le=MAX_MAX_STRESS)
    conditions: tuple[StoryCondition, ...] = ()
    growth_marks: int = Field(default=0, ge=0, le=GROWTH_REQUIRED)

    @property
    def taken_out(self) -> bool:
        return self.stress == self.max_stress

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.stress > self.max_stress:
            raise ValueError("stress cannot exceed maximum stress")
        _unique_tag_ids(self.tags)
        condition_ids = [condition.id for condition in self.conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("Story condition ids must be unique")
        return self


class StoryGearTag(Frozen):
    name: str
    description: str


class StoryItemState(Mutable):
    gear: StoryGearTag | None = None


class StoryCharacterData(Frozen):
    approaches: StoryApproaches
    tags: tuple[StoryActorTag, ...] = ()
    max_stress: int = Field(default=5, ge=MIN_MAX_STRESS, le=MAX_MAX_STRESS)

    @model_validator(mode="after")
    def _initial_limits(self) -> Self:
        approaches = self.approaches
        scores = (approaches.bold, approaches.subtle, approaches.clever, approaches.empathetic)
        if any(score > 2 for score in scores):
            raise ValueError("initial Story approaches cannot exceed +2")
        _unique_tag_ids(self.tags)
        return self


class StoryActorDefinition(Frozen):
    approaches: StoryApproaches = StoryApproaches(
        bold=0,
        subtle=0,
        clever=0,
        empathetic=0,
    )
    tags: tuple[StoryActorTag, ...] = ()
    stress: int = Field(default=0, ge=0)
    max_stress: int = Field(default=5, ge=MIN_MAX_STRESS, le=MAX_MAX_STRESS)
    conditions: tuple[StoryCondition, ...] = ()

    def runtime(self) -> StoryActorState:
        return StoryActorState(
            approaches=self.approaches,
            tags=self.tags,
            stress=self.stress,
            max_stress=self.max_stress,
            conditions=self.conditions,
        )


class StoryItemDefinition(Frozen):
    gear: StoryGearTag | None = None

    def runtime(self) -> StoryItemState:
        return StoryItemState(gear=self.gear)


DEFAULT_APPROACHES = StoryApproaches(bold=0, subtle=0, clever=0, empathetic=0)


def actor_state(rules: Rules) -> StoryActorState:
    return StoryActorState.model_validate(rules)


def item_state(rules: Rules) -> StoryItemState:
    return StoryItemState.model_validate(rules)


def read_actor(state: GameState, actor_id: EntityId) -> StoryActorState:
    """A detached copy: nothing lands in the record until `write_actor` dumps it back."""
    return actor_state(state.world.record(actor_id, "actor").rules)


def write_actor(state: GameState, actor_id: EntityId, sheet: StoryActorState) -> None:
    state.world.record(actor_id, "actor").rules = sheet.model_dump(mode="json")


def read_item(state: GameState, item_id: EntityId) -> StoryItemState:
    return item_state(state.world.record(item_id, "item").rules)


def player_state(state: GameState) -> StoryActorState:
    return read_actor(state, PLAYER_ID)
