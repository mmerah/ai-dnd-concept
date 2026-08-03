from random import Random
from typing import Annotated, Literal, TypeGuard

from pydantic import Field

from aidm.advancement import AdvancementStatus
from aidm.base import PLAYER_ID, AdvancementDecision, Frozen, ItemEntity, Slug, slug
from aidm.transition import Transition
from aidm.world import GameState

from .access import story_state
from .facts import (
    ApproachRaised,
    Emitted,
    GearAcquired,
    GrowthReset,
    MaximumStressIncreased,
    Revived,
    TagAdded,
    TagRemoved,
    TagRewritten,
)
from .state import (
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


class RaiseApproach(AdvancementDecision):
    choice: Literal["raise_approach"] = "raise_approach"
    approach: StoryApproach


class AddTag(AdvancementDecision):
    choice: Literal["add_tag"] = "add_tag"
    id: Slug
    name: str
    kind: Literal["edge", "bond"]
    description: str


class RemoveBurden(AdvancementDecision):
    choice: Literal["remove_burden"] = "remove_burden"
    id: Slug


class RewriteBurden(AdvancementDecision):
    choice: Literal["rewrite_burden"] = "rewrite_burden"
    id: Slug
    name: str
    description: str


class AcquireGear(AdvancementDecision):
    choice: Literal["acquire_gear"] = "acquire_gear"
    item_name: str
    item_brief: str
    gear: StoryGearTag


class IncreaseMaximumStress(AdvancementDecision):
    choice: Literal["increase_maximum_stress"] = "increase_maximum_stress"


type StoryAdvancementDecision = Annotated[
    RaiseApproach | AddTag | RemoveBurden | RewriteBurden | AcquireGear | IncreaseMaximumStress,
    Field(discriminator="choice"),
]


def is_story_decision(value: object) -> TypeGuard[StoryAdvancementDecision]:
    return isinstance(
        value,
        RaiseApproach | AddTag | RemoveBurden | RewriteBurden | AcquireGear | IncreaseMaximumStress,
    )


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

    def preview(self, state: GameState) -> StoryAdvancementPreview:
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

    def plan(
        self,
        state: GameState,
        decision: StoryAdvancementDecision,
    ) -> StoryAdvancementPlan:
        player = self._ready(state)
        self._validate_choice(player, decision)
        summary = self._describe_choice(player, decision)
        return StoryAdvancementPlan(decision=decision, summary=summary)

    def advance(
        self,
        state: GameState,
        decision: StoryAdvancementDecision,
        rng: Random,
    ) -> Transition:
        del rng
        draft = state.draft()
        player = self._ready(draft)
        self._validate_choice(player, decision)
        facts: list[Emitted] = self._apply(draft, player, decision)
        player.growth_marks = 0
        return Transition(state=draft.committed(), facts=(*facts, GrowthReset()))

    def _apply(
        self,
        draft: GameState,
        player: StoryActorState,
        decision: StoryAdvancementDecision,
    ) -> list[Emitted]:
        match decision:
            case RaiseApproach(approach=approach):
                before = player.approaches.score(approach)
                player.approaches = player.approaches.model_copy(update={approach: before + 1})
                return [ApproachRaised(approach=approach, before=before, after=before + 1)]
            case AddTag():
                tag = StoryActorTag(
                    id=decision.id,
                    name=decision.name,
                    kind=decision.kind,
                    description=decision.description,
                )
                player.tags = (*player.tags, tag)
                return [TagAdded(tag=tag)]
            case RemoveBurden(id=tag_id):
                burden = self._burden(player, tag_id)
                player.tags = tuple(tag for tag in player.tags if tag.id != burden.id)
                return [TagRemoved(tag=burden)]
            case RewriteBurden(id=tag_id):
                before_tag = self._burden(player, tag_id)
                after_tag = StoryActorTag(
                    id=before_tag.id,
                    name=decision.name,
                    kind="burden",
                    description=decision.description,
                )
                player.tags = tuple(
                    after_tag if tag.id == before_tag.id else tag for tag in player.tags
                )
                return [TagRewritten(before=before_tag, after=after_tag)]
            case AcquireGear():
                item = ItemEntity(
                    id=slug(decision.item_name, draft.world.entities),
                    name=decision.item_name,
                    brief=decision.item_brief,
                    known=True,
                    container_id=PLAYER_ID,
                )
                created = draft.add(item)
                story_state(draft).items[item.id] = StoryItemState(gear=decision.gear)
                return [
                    created,
                    GearAcquired(item_id=item.id, item_name=item.name, gear=decision.gear),
                ]
            case IncreaseMaximumStress():
                before_max = player.max_stress
                player.max_stress = before_max + 1
                raised: list[Emitted] = [
                    MaximumStressIncreased(before=before_max, after=player.max_stress)
                ]
                if player.stress == before_max:
                    raised.append(Revived(actor_id=PLAYER_ID, actor_name=draft.player.name))
                return raised

    def _ready(self, state: GameState) -> StoryActorState:
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
        return story_state(state).actor(PLAYER_ID)
