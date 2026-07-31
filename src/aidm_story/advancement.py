from random import Random
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, Field, TypeAdapter

from aidm.domain.base import PLAYER_ID, Slug, slug
from aidm.domain.engine import AdvancementStatus
from aidm.domain.entities import ItemEntity
from aidm.domain.events import EntityCreated, Event
from aidm.domain.state import GameState
from aidm.utils.models import Frozen

from .codecs import ACTOR_STATE_CODEC, ITEM_STATE_CODEC
from .constants import ENGINE_ID, SCHEMA_VERSION
from .events import (
    ApproachRaised,
    GrowthReset,
    MaximumStressIncreased,
    Revived,
    TagAdded,
    TagRemoved,
    TagRewritten,
    encode_story_event,
)
from .models import (
    GROWTH_REQUIRED,
    MAX_APPROACH,
    MAX_MAX_STRESS,
    StoryActorState,
    StoryActorTag,
    StoryApproach,
    StoryApproaches,
    StoryGearTag,
    StoryItemState,
)


class RaiseApproach(Frozen):
    choice: Literal["raise_approach"] = "raise_approach"
    approach: StoryApproach


class AddTag(Frozen):
    choice: Literal["add_tag"] = "add_tag"
    id: Slug
    name: str
    kind: Literal["edge", "bond"]
    description: str


class RemoveBurden(Frozen):
    choice: Literal["remove_burden"] = "remove_burden"
    id: Slug


class RewriteBurden(Frozen):
    choice: Literal["rewrite_burden"] = "rewrite_burden"
    id: Slug
    name: str
    description: str


class AcquireGear(Frozen):
    choice: Literal["acquire_gear"] = "acquire_gear"
    item_name: str
    item_brief: str
    gear: StoryGearTag


class IncreaseMaximumStress(Frozen):
    choice: Literal["increase_maximum_stress"] = "increase_maximum_stress"


type StoryAdvancementDecision = Annotated[
    RaiseApproach | AddTag | RemoveBurden | RewriteBurden | AcquireGear | IncreaseMaximumStress,
    Field(discriminator="choice"),
]
DECISION_ADAPTER: TypeAdapter[StoryAdvancementDecision] = TypeAdapter(StoryAdvancementDecision)
DECISION_TYPES: tuple[type, ...] = get_args(get_args(StoryAdvancementDecision.__value__)[0])


class StoryAdvancementPreview(Frozen):
    approaches: StoryApproaches
    tags: tuple[StoryActorTag, ...]
    max_stress: int
    approach_limit: int = MAX_APPROACH
    max_stress_limit: int = MAX_MAX_STRESS


class StoryAdvancementPlan(Frozen):
    decision: StoryAdvancementDecision
    summary: str


class StoryAdvancement:
    def available(self, state: GameState) -> bool:
        return self._player(state).growth_marks == GROWTH_REQUIRED

    def preview(self, state: GameState) -> BaseModel:
        player = self._player(state)
        if player.growth_marks != GROWTH_REQUIRED:
            raise ValueError(f"Story advancement requires {GROWTH_REQUIRED} growth marks")
        return StoryAdvancementPreview(
            approaches=player.approaches,
            tags=player.tags,
            max_stress=player.max_stress,
        )

    def status(self, state: GameState) -> AdvancementStatus:
        player = self._player(state)
        if player.growth_marks < GROWTH_REQUIRED:
            return AdvancementStatus(
                headline="Story growth",
                detail=(
                    f"{player.growth_marks} of {GROWTH_REQUIRED} growth marks.",
                    "A setback on a player risk earns growth.",
                ),
                progress=player.growth_marks / GROWTH_REQUIRED,
            )
        return AdvancementStatus(
            headline="Story growth ready",
            detail=(f"{GROWTH_REQUIRED} of {GROWTH_REQUIRED} growth marks.",),
            progress=1.0,
        )

    def plan(self, state: GameState, decisions: BaseModel) -> BaseModel:
        player = self._ready(state, decisions)
        decision = DECISION_ADAPTER.validate_python(decisions)
        self._validate_choice(player, decision)
        summary = self._describe_choice(player, decision)
        return StoryAdvancementPlan(decision=decision, summary=summary)

    def advance(
        self,
        state: GameState,
        decisions: BaseModel,
        rng: Random,
    ) -> list[Event]:
        del rng
        player = self._ready(state, decisions)
        decision = DECISION_ADAPTER.validate_python(decisions)
        self._validate_choice(player, decision)
        events: list[Event]
        match decision:
            case RaiseApproach(approach=approach):
                before = player.approaches.score(approach)
                events = [
                    encode_story_event(
                        ApproachRaised(approach=approach, before=before, after=before + 1),
                        ENGINE_ID,
                        SCHEMA_VERSION,
                    )
                ]
            case AddTag():
                events = [
                    encode_story_event(
                        TagAdded(
                            tag=StoryActorTag(
                                id=decision.id,
                                name=decision.name,
                                kind=decision.kind,
                                description=decision.description,
                            )
                        ),
                        ENGINE_ID,
                        SCHEMA_VERSION,
                    )
                ]
            case RemoveBurden(id=tag_id):
                events = [
                    encode_story_event(
                        TagRemoved(tag=self._burden(player, tag_id)), ENGINE_ID, SCHEMA_VERSION
                    )
                ]
            case RewriteBurden(id=tag_id):
                before = self._burden(player, tag_id)
                events = [
                    encode_story_event(
                        TagRewritten(
                            before=before,
                            after=StoryActorTag(
                                id=before.id,
                                name=decision.name,
                                kind="burden",
                                description=decision.description,
                            ),
                        ),
                        ENGINE_ID,
                        SCHEMA_VERSION,
                    )
                ]
            case AcquireGear():
                item = ItemEntity(
                    id=slug(decision.item_name, state.world.entities),
                    name=decision.item_name,
                    brief=decision.item_brief,
                    known=True,
                    authored=False,
                    container_id=PLAYER_ID,
                    rules=ITEM_STATE_CODEC.encode(StoryItemState(gear=decision.gear)),
                )
                events = [EntityCreated(entity=item)]
            case IncreaseMaximumStress():
                after_max = player.max_stress + 1
                events = [
                    encode_story_event(
                        MaximumStressIncreased(before=player.max_stress, after=after_max),
                        ENGINE_ID,
                        SCHEMA_VERSION,
                    )
                ]
                if player.taken_out:
                    events.append(
                        encode_story_event(
                            Revived(actor_id=PLAYER_ID, actor_name=state.player.name),
                            ENGINE_ID,
                            SCHEMA_VERSION,
                        )
                    )
        return [*events, encode_story_event(GrowthReset(), ENGINE_ID, SCHEMA_VERSION)]

    def _ready(
        self,
        state: GameState,
        decisions: BaseModel,
    ) -> StoryActorState:
        if not isinstance(decisions, DECISION_TYPES):
            raise TypeError(f"Story advancement received {type(decisions).__name__}")
        player = self._player(state)
        if player.growth_marks != GROWTH_REQUIRED:
            raise ValueError(f"Story advancement requires {GROWTH_REQUIRED} growth marks")
        return player

    @staticmethod
    def _validate_choice(
        player: StoryActorState,
        decision: StoryAdvancementDecision,
    ) -> None:
        match decision:
            case RaiseApproach(approach=approach):
                if player.approaches.score(approach) >= MAX_APPROACH:
                    raise ValueError(f"{approach} is already at +3")
            case AddTag(id=tag_id):
                if any(tag.id == tag_id for tag in player.tags):
                    raise ValueError(f"Story tag id {tag_id!r} already exists")
            case RemoveBurden(id=tag_id) | RewriteBurden(id=tag_id):
                StoryAdvancement._burden(player, tag_id)
            case AcquireGear():
                pass
            case IncreaseMaximumStress():
                if player.max_stress >= MAX_MAX_STRESS:
                    raise ValueError(f"maximum stress is already {MAX_MAX_STRESS}")

    @staticmethod
    def _describe_choice(
        player: StoryActorState,
        decision: StoryAdvancementDecision,
    ) -> str:
        match decision:
            case RaiseApproach(approach=approach):
                before = player.approaches.score(approach)
                return f"raise {approach} from {before:+d} to {before + 1:+d}"
            case AddTag(kind=kind, name=name):
                return f"add {kind} {name}"
            case RemoveBurden(id=tag_id):
                return f"remove burden {StoryAdvancement._burden(player, tag_id).name}"
            case RewriteBurden(id=tag_id, name=name):
                return f"rewrite burden {tag_id} as {name}"
            case AcquireGear(item_name=item_name):
                return f"acquire gear {item_name}"
            case IncreaseMaximumStress():
                return f"increase maximum stress to {player.max_stress + 1}"

    @staticmethod
    def _burden(player: StoryActorState, tag_id: Slug) -> StoryActorTag:
        burden = next(
            (tag for tag in player.tags if tag.id == tag_id and tag.kind == "burden"),
            None,
        )
        if burden is None:
            raise ValueError(f"active burden {tag_id!r} does not exist")
        return burden

    @staticmethod
    def _player(state: GameState) -> StoryActorState:
        rules = state.player.rules
        if rules is None:
            raise ValueError("Story player has no rules data")
        return ACTOR_STATE_CODEC.decode(rules)
