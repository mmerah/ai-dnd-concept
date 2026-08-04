from typing import Literal

from aidm.kernel.base import Entity
from aidm.kernel.facts import Fact

from .identity import ENGINE_ID
from .state import GROWTH_REQUIRED, StoryApproach, StoryCondition

StoryOutcome = Literal["strong", "mixed", "setback"]
STRONG_TOTAL = 10
MIXED_TOTAL = 7


def outcome_of(total: int) -> StoryOutcome:
    if total >= STRONG_TOTAL:
        return "strong"
    return "mixed" if total >= MIXED_TOTAL else "setback"


def risk_rolled(
    actor: Entity,
    dice: tuple[int, int],
    approach: StoryApproach,
    approach_modifier: int,
    helpful_modifier: int,
    hindering_modifier: int,
    difficulty: int,
    total: int,
    outcome: StoryOutcome,
) -> Fact:
    modifiers = approach_modifier + helpful_modifier + hindering_modifier - difficulty
    trace = f"{actor.name} risk: {dice[0]}+{dice[1]} {modifiers:+d} = {total}: {outcome}"
    return Fact(
        source=ENGINE_ID,
        kind="risk_rolled",
        trace=trace,
        narrator=f"{actor.name}'s attempt ends in a {outcome}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "dice": list(dice),
            "approach": approach,
            "approach_modifier": approach_modifier,
            "helpful_modifier": helpful_modifier,
            "hindering_modifier": hindering_modifier,
            "difficulty": difficulty,
            "total": total,
            "outcome": outcome,
        },
    )


def stress_changed(actor: Entity, before: int, after: int, maximum: int) -> Fact:
    narrator = (
        f"{actor.name} recovers some composure"
        if after < before
        else f"{actor.name} comes under more pressure"
    )
    return Fact(
        source=ENGINE_ID,
        kind="stress_changed",
        trace=f"{actor.name} stress {before}->{after}/{maximum}",
        narrator=narrator,
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "before": before,
            "after": after,
            "maximum": maximum,
        },
    )


def taken_out(actor: Entity) -> Fact:
    trace = f"{actor.name} is taken out"
    return Fact(
        source=ENGINE_ID,
        kind="taken_out",
        trace=trace,
        narrator=trace,
        data={"actor_id": actor.id, "actor_name": actor.name},
    )


def revived(actor: Entity) -> Fact:
    trace = f"{actor.name} is no longer taken out"
    return Fact(
        source=ENGINE_ID,
        kind="revived",
        trace=trace,
        narrator=trace,
        data={"actor_id": actor.id, "actor_name": actor.name},
    )


def condition_applied(actor: Entity, condition: StoryCondition) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="condition_applied",
        trace=f"{actor.name} gains condition {condition.name}[id={condition.id}]",
        narrator=f"{actor.name} is now {condition.name}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "condition_id": condition.id,
            "condition_name": condition.name,
        },
    )


def condition_cleared(actor: Entity, condition: StoryCondition) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="condition_cleared",
        trace=f"{actor.name} loses condition {condition.name}[id={condition.id}]",
        narrator=f"{actor.name} is no longer {condition.name}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "condition_id": condition.id,
            "condition_name": condition.name,
        },
    )


def growth_marked(before: int, after: int) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="growth_marked",
        trace=f"growth {before}->{after}/{GROWTH_REQUIRED}",
        narrator=None,
        data={"before": before, "after": after, "required": GROWTH_REQUIRED},
    )
