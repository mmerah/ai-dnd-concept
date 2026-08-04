from typing import Annotated

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from aidm.base import PLAYER_ID, Entity, EntityId, Slug
from aidm.facts import Fact
from aidm.tools import TurnContext, require_actor_here, require_kind

from . import rules
from .state import (
    GROWTH_REQUIRED,
    StoryActorState,
    StoryApproach,
    StoryCondition,
    read_actor,
    read_item,
    write_actor,
)

DIRECTOR_INSTRUCTIONS = """Story uses stress and conditions instead of hit points. Stress tracks \
mounting harm and pressure; reaching maximum stress takes an actor out, and only `recover_stress` \
brings them back. Conditions hold persistent injuries and statuses with concrete fictional effects.

Call `risk` whenever success is uncertain and both success and failure would change the fiction. \
It decides the outcome and tells you which it is; you then apply what follows with further calls. \
Effects that happen whatever the outcome need no risk at all. A setback on a player risk marks \
growth automatically."""

ActorArg = Annotated[
    EntityId | None,
    Field(description="Exact id of the affected actor; omit for the player."),
]


def _actor(deps: TurnContext, actor_id: EntityId | None) -> tuple[Entity, StoryActorState]:
    actor = require_actor_here(deps.draft, actor_id)
    if actor.id != PLAYER_ID and not actor.known:
        raise ModelRetry(f"actor {actor.id!r} has not been revealed")
    return actor, read_actor(deps.draft, actor.id)


def _tag_modifier(sheet: StoryActorState, tag_id: Slug, kinds: tuple[str, ...]) -> None:
    tag = next((tag for tag in sheet.tags if tag.id == tag_id), None)
    if tag is None or tag.kind not in kinds:
        raise ModelRetry(f"tag {tag_id!r} is not an active {' or '.join(kinds)} on this actor")


def _require_condition(sheet: StoryActorState, condition_id: Slug) -> StoryCondition:
    condition = next((item for item in sheet.conditions if item.id == condition_id), None)
    if condition is None:
        raise ModelRetry(f"condition {condition_id!r} is not active on this actor")
    return condition


def _helpful_modifier(
    deps: TurnContext,
    actor: Entity,
    sheet: StoryActorState,
    tag_id: Slug | None,
    gear_id: EntityId | None,
) -> int:
    if tag_id is not None and gear_id is not None:
        raise ModelRetry("a risk takes at most one helpful factor: a tag or a carried gear item")
    if tag_id is not None:
        _tag_modifier(sheet, tag_id, ("edge", "bond"))
        return 1
    if gear_id is not None:
        item = require_kind(deps.draft, gear_id, "item")
        if item.parent_id != actor.id:
            raise ModelRetry(f"gear item {gear_id!r} is not carried by {actor.id!r}")
        if read_item(deps.draft, gear_id).gear is None:
            raise ModelRetry(f"item {gear_id!r} has no Story gear benefit")
        return 1
    return 0


def _hindering_modifier(
    sheet: StoryActorState,
    burden_id: Slug | None,
    condition_id: Slug | None,
) -> int:
    if burden_id is not None and condition_id is not None:
        raise ModelRetry("a risk takes at most one hindering factor: a burden or a condition")
    if burden_id is not None:
        _tag_modifier(sheet, burden_id, ("burden",))
        return -1
    if condition_id is not None:
        _ = _require_condition(sheet, condition_id)
        return -1
    return 0


def risk(
    ctx: RunContext[TurnContext],
    approach: Annotated[
        StoryApproach,
        Field(description="How the actor acts: bold, subtle, clever, or empathetic."),
    ],
    difficulty: Annotated[
        int, Field(ge=0, le=2, description="0 risky, 1 demanding, or 2 extreme.")
    ],
    actor_id: Annotated[
        EntityId | None,
        Field(description="Exact id of the actor taking the risk; omit for the player."),
    ] = None,
    helpful_tag_id: Annotated[
        Slug | None,
        Field(description="Exact id of a directly relevant active edge or bond on the actor."),
    ] = None,
    helpful_gear_id: Annotated[
        EntityId | None,
        Field(description="Exact id of a carried item whose shown gear benefit directly helps."),
    ] = None,
    hindering_burden_id: Annotated[
        Slug | None,
        Field(description="Exact id of a directly relevant active burden on the actor."),
    ] = None,
    hindering_condition_id: Annotated[
        Slug | None,
        Field(description="Exact id of a directly relevant active condition on the actor."),
    ] = None,
) -> str:
    """Resolve an uncertain action whose result matters, and report the outcome.

    Use only when success is uncertain and both success and failure would change the fiction. The
    roll decides between a strong outcome, a mixed one, and a setback; apply what follows with
    further calls. At most one helpful and one hindering factor count.
    """
    deps = ctx.deps
    actor, sheet = _actor(deps, actor_id)
    if sheet.taken_out:
        raise ModelRetry(
            f"actor {actor.id!r} is taken out and cannot attempt a risk;"
            " recover_stress must bring them back below max_stress first"
        )
    helpful = _helpful_modifier(deps, actor, sheet, helpful_tag_id, helpful_gear_id)
    hindering = _hindering_modifier(sheet, hindering_burden_id, hindering_condition_id)
    dice = (deps.rng.randint(1, 6), deps.rng.randint(1, 6))
    score = sheet.approaches.score(approach)
    total = sum(dice) + score + helpful + hindering - difficulty
    outcome = rules.outcome_of(total)
    facts = [
        rules.risk_rolled(
            actor, dice, approach, score, helpful, hindering, difficulty, total, outcome
        )
    ]
    if outcome == "setback" and actor.id == PLAYER_ID and sheet.growth_marks < GROWTH_REQUIRED:
        before = sheet.growth_marks
        sheet.growth_marks = before + 1
        facts.append(rules.growth_marked(before, sheet.growth_marks))
    write_actor(deps.draft, actor.id, sheet)
    return deps.record(facts)


def take_stress(
    ctx: RunContext[TurnContext],
    amount: Annotated[int, Field(gt=0, description="Positive stress gained.")],
    actor_id: ActorArg = None,
) -> str:
    """Increase an actor's pressure and possibly take them out.

    Use for harm, exhaustion, fear, or pressure that pushes an actor toward defeat. Reaching
    maximum stress takes them out.
    """
    deps = ctx.deps
    actor, sheet = _actor(deps, actor_id)
    if sheet.stress == sheet.max_stress:
        return deps.record([])
    before = sheet.stress
    sheet.stress = min(sheet.max_stress, before + amount)
    facts: list[Fact] = [rules.stress_changed(actor, before, sheet.stress, sheet.max_stress)]
    if sheet.taken_out:
        facts.append(rules.taken_out(actor))
    write_actor(deps.draft, actor.id, sheet)
    return deps.record(facts)


def recover_stress(
    ctx: RunContext[TurnContext],
    amount: Annotated[int, Field(gt=0, description="Positive stress recovered.")],
    actor_id: ActorArg = None,
) -> str:
    """Reduce an actor's pressure and return a taken-out actor to action.

    Use only when the fiction provides meaningful rest, safety, comfort, treatment, or another
    release from pressure. It is the only way a taken-out actor returns once stress drops below
    maximum.
    """
    deps = ctx.deps
    actor, sheet = _actor(deps, actor_id)
    if sheet.stress == 0:
        return deps.record([])
    before = sheet.stress
    sheet.stress = max(0, before - amount)
    facts: list[Fact] = [rules.stress_changed(actor, before, sheet.stress, sheet.max_stress)]
    if before == sheet.max_stress and not sheet.taken_out:
        facts.append(rules.revived(actor))
    write_actor(deps.draft, actor.id, sheet)
    return deps.record(facts)


def apply_condition(
    ctx: RunContext[TurnContext],
    condition: Annotated[
        StoryCondition, Field(description="The persistent injury or status to record.")
    ],
    actor_id: ActorArg = None,
) -> str:
    """Record a persistent injury, status, or other concrete fictional constraint.

    Use when an injury or status should remain true after this turn and affect later action, such
    as `Twisted Ankle`, `Terrified`, or `Pinned Beneath Rubble`. Give it a stable slug id, concise
    name, and description of the concrete constraint.
    """
    deps = ctx.deps
    actor, sheet = _actor(deps, actor_id)
    if any(active.id == condition.id for active in sheet.conditions):
        return deps.record([])
    sheet.conditions = (*sheet.conditions, condition)
    write_actor(deps.draft, actor.id, sheet)
    return deps.record([rules.condition_applied(actor, condition)])


def clear_condition(
    ctx: RunContext[TurnContext],
    condition_id: Annotated[Slug, Field(description="Exact id of the active condition to remove.")],
    actor_id: ActorArg = None,
) -> str:
    """Remove a persistent injury or status that the fiction resolves.

    Use when treatment, escape, recovery, or another established change ends an active condition.
    Copy its exact shown condition id.
    """
    deps = ctx.deps
    actor, sheet = _actor(deps, actor_id)
    condition = _require_condition(sheet, condition_id)
    sheet.conditions = tuple(item for item in sheet.conditions if item.id != condition.id)
    write_actor(deps.draft, actor.id, sheet)
    return deps.record([rules.condition_cleared(actor, condition)])


def story_toolset() -> FunctionToolset[TurnContext]:
    return FunctionToolset[TurnContext](
        [risk, take_stress, recover_stress, apply_condition, clear_condition]
    )
