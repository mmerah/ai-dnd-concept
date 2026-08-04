from random import Random
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from aidm.core.base import (
    PLAYER_ID,
    AdvancementDecision,
    Entity,
    EntityId,
    Frozen,
    Slug,
    slug,
)
from aidm.core.engine import Transition
from aidm.core.facts import Fact
from aidm.core.world import EngineRules, GameState

from .identity import ENGINE_ID
from .rules import revived
from .state import (
    APPROACH_NAMES,
    GROWTH_REQUIRED,
    MAX_APPROACH,
    MAX_MAX_STRESS,
    StoryActorState,
    StoryActorTag,
    StoryApproach,
    StoryGearTag,
    StoryItemState,
    StoryRules,
    StoryState,
    actor_of,
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


def dump_decision(decision: StoryAdvancementDecision) -> AdvancementDecision:
    """The UI mints the typed choice; core carries only the blob."""
    return AdvancementDecision(engine=ENGINE_ID, choice=decision.model_dump(mode="json"))


def load_decision(decision: AdvancementDecision) -> StoryAdvancementDecision:
    if decision.engine != ENGINE_ID:
        raise ValueError(f"Story received a {decision.engine!r} decision")
    return DECISION_ADAPTER.validate_python(decision.choice)


def _approach_raised(approach: StoryApproach, before: int, after: int) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="approach_raised",
        trace=f"{approach} {before:+d}->{after:+d}",
        narrator=f"the player's {approach} approach improves",
        data={"approach": approach, "before": before, "after": after},
    )


def _tag_added(tag: StoryActorTag) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="tag_added",
        trace=f"tag added: {tag.name}[id={tag.id}, {tag.kind}]",
        narrator=f"the player gains {tag.name}",
        data={"tag_id": tag.id, "tag_name": tag.name, "kind": tag.kind},
    )


def _tag_removed(tag: StoryActorTag) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="tag_removed",
        trace=f"tag removed: {tag.name}[id={tag.id}]",
        narrator=f"the player leaves {tag.name} behind",
        data={"tag_id": tag.id, "tag_name": tag.name},
    )


def _tag_rewritten(before: StoryActorTag, after: StoryActorTag) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="tag_rewritten",
        trace=f"tag rewritten: {before.name}[id={before.id}] -> {after.name}",
        narrator=f"the player's burden becomes {after.name}",
        data={"tag_id": before.id, "before_name": before.name, "after_name": after.name},
    )


def _gear_acquired(item_id: EntityId, item_name: str, gear: StoryGearTag) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="gear_acquired",
        trace=f"gear acquired: {item_name} ({gear.name})",
        narrator=f"the player now carries {item_name}",
        data={"item_id": item_id, "item_name": item_name, "gear_name": gear.name},
    )


def _maximum_stress_increased(before: int, after: int) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="maximum_stress_increased",
        trace=f"max stress {before}->{after}",
        narrator="the player becomes more resilient",
        data={"before": before, "after": after},
    )


def _growth_reset() -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="growth_reset",
        trace=f"growth reset from {GROWTH_REQUIRED}/{GROWTH_REQUIRED}",
        narrator=None,
        data={"before": GROWTH_REQUIRED},
    )


def _require_full_growth(player: StoryActorState) -> None:
    if player.growth_marks != GROWTH_REQUIRED:
        raise ValueError(f"Story advancement requires {GROWTH_REQUIRED} growth marks")


def raisable_approaches(player: StoryActorState) -> tuple[tuple[StoryApproach, int], ...]:
    """Each approach still under the cap with its current score."""
    return tuple(
        (name, score)
        for name in APPROACH_NAMES
        if (score := player.approaches.score(name)) < MAX_APPROACH
    )


def burdens(player: StoryActorState) -> tuple[StoryActorTag, ...]:
    return tuple(tag for tag in player.tags if tag.kind == "burden")


def stress_raisable(player: StoryActorState) -> bool:
    return player.max_stress < MAX_MAX_STRESS


def validate_choice(player: StoryActorState, decision: StoryAdvancementDecision) -> None:
    match decision:
        case RaiseApproach(approach=approach):
            if player.approaches.score(approach) >= MAX_APPROACH:
                raise ValueError(f"{approach} is already at +3")
        case AddTag(id=tag_id):
            if any(tag.id == tag_id for tag in player.tags):
                raise ValueError(f"Story tag id {tag_id!r} already exists")
        case RemoveBurden(id=tag_id) | RewriteBurden(id=tag_id):
            _burden(player, tag_id)
        case AcquireGear():
            pass
        case IncreaseMaximumStress():
            if player.max_stress >= MAX_MAX_STRESS:
                raise ValueError(f"maximum stress is already {MAX_MAX_STRESS}")


def describe_choice(player: StoryActorState, decision: StoryAdvancementDecision) -> str:
    match decision:
        case RaiseApproach(approach=approach):
            before = player.approaches.score(approach)
            return f"raise {approach} from {before:+d} to {before + 1:+d}"
        case AddTag(kind=kind, name=name):
            return f"add {kind} {name}"
        case RemoveBurden(id=tag_id):
            return f"remove burden {_burden(player, tag_id).name}"
        case RewriteBurden(id=tag_id, name=name):
            return f"rewrite burden {tag_id} as {name}"
        case AcquireGear(item_name=item_name):
            return f"acquire gear {item_name}"
        case IncreaseMaximumStress():
            return f"increase maximum stress to {player.max_stress + 1}"


def _burden(player: StoryActorState, tag_id: Slug) -> StoryActorTag:
    found = next(
        (tag for tag in player.tags if tag.id == tag_id and tag.kind == "burden"),
        None,
    )
    if found is None:
        raise ValueError(f"active burden {tag_id!r} does not exist")
    return found


def available[R: EngineRules](state: GameState[R]) -> bool:
    return actor_of(state, PLAYER_ID).growth_marks == GROWTH_REQUIRED


def advance(
    decision: AdvancementDecision, state: StoryState, rng: Random
) -> Transition[StoryRules]:
    del rng
    typed = load_decision(decision)
    draft = state.draft()
    player = actor_of(draft, PLAYER_ID)
    _require_full_growth(player)
    validate_choice(player, typed)
    facts = _apply(draft, player, typed)
    player.growth_marks = 0
    return Transition(state=draft.committed(), facts=(*facts, _growth_reset()))


def _apply(
    draft: StoryState,
    player: StoryActorState,
    decision: StoryAdvancementDecision,
) -> list[Fact]:
    match decision:
        case RaiseApproach(approach=approach):
            before = player.approaches.score(approach)
            player.approaches = player.approaches.model_copy(update={approach: before + 1})
            return [_approach_raised(approach, before, before + 1)]
        case AddTag():
            tag = StoryActorTag(
                id=decision.id,
                name=decision.name,
                kind=decision.kind,
                description=decision.description,
            )
            player.tags = (*player.tags, tag)
            return [_tag_added(tag)]
        case RemoveBurden(id=tag_id):
            burden_tag = _burden(player, tag_id)
            player.tags = tuple(tag for tag in player.tags if tag.id != burden_tag.id)
            return [_tag_removed(burden_tag)]
        case RewriteBurden(id=tag_id):
            before_tag = _burden(player, tag_id)
            after_tag = StoryActorTag(
                id=before_tag.id,
                name=decision.name,
                kind="burden",
                description=decision.description,
            )
            player.tags = tuple(
                after_tag if tag.id == before_tag.id else tag for tag in player.tags
            )
            return [_tag_rewritten(before_tag, after_tag)]
        case AcquireGear():
            item = Entity(
                id=slug(decision.item_name, draft.world.all_ids()),
                kind="item",
                name=decision.item_name,
                brief=decision.item_brief,
                known=True,
                parent_id=PLAYER_ID,
            )
            created = draft.add(item, StoryItemState(gear=decision.gear))
            return [created, _gear_acquired(item.id, item.name, decision.gear)]
        case IncreaseMaximumStress():
            before_max = player.max_stress
            player.max_stress = before_max + 1
            raised: list[Fact] = [_maximum_stress_increased(before_max, player.max_stress)]
            if player.stress == before_max:
                raised.append(revived(draft.player))
            return raised
