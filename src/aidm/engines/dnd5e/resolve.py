from collections.abc import Sequence
from random import Random

from aidm.actions import is_world_action, resolve_world_action
from aidm.content import Rules
from aidm.facts import Fact

from . import features, progression, rolls, spells
from .access import Dnd5eWorld
from .content.vocabulary import RestType
from .direction import (
    ApplyCondition,
    Attack,
    Cast,
    Consequence,
    Damage,
    DcRoll,
    Heal,
    LevelUp,
    Rest,
    RollCheck,
    RollSave,
    UseFeature,
)
from .identity import ENGINE_ID
from .mechanics import combat, common, conditions, health
from .mechanics.resolution import Resolution
from .ruleset import Ruleset
from .state import Dnd5eItemState


def resolve(
    mechanics: Sequence[Consequence], world: Dnd5eWorld, rng: Random, ruleset: Ruleset
) -> list[Fact]:
    return _fold(Resolution(world=world, rng=rng, ruleset=ruleset), mechanics)


def _fold(ctx: Resolution, mechanics: Sequence[Consequence]) -> list[Fact]:
    facts: list[Fact] = []
    for consequence in mechanics:
        facts.extend(_walk(ctx, consequence))
    return facts


def _walk(ctx: Resolution, consequence: Consequence) -> list[Fact]:
    if is_world_action(consequence):
        return list(resolve_world_action(consequence, ctx.draft, _improvised_item_rules))
    match consequence:
        case RollCheck(ability=ability, dc=dc):
            rolled = rolls.roll_check(ctx.player, ability, dc, ctx.rng)
            return _branched(ctx, consequence, (), rolled)
        case RollSave(ability=ability, dc=dc, target_id=target_id):
            target = ctx.target(target_id)
            rolled = rolls.roll_save(target, ability, dc, ctx.rng)
            return _branched(ctx, consequence, common.reveal(ctx, target), rolled)
        case Attack():
            return combat.attack(ctx, consequence)
        case LevelUp():
            return progression.offer(ctx.player)
        case UseFeature():
            return features.use(ctx, consequence)
        case Cast():
            return spells.cast(ctx, consequence)
        case Rest(rest=rest):
            return [_rested(ctx, rest)]
        case Damage():
            return health.damage(ctx, consequence)
        case Heal():
            return health.heal(ctx, consequence)
        case ApplyCondition():
            return conditions.change(ctx, consequence)
        case _:
            raise TypeError(f"unsupported 5e consequence {type(consequence).__name__}")


def _improvised_item_rules() -> Rules:
    return Dnd5eItemState().model_dump(mode="json")


def _branched(
    ctx: Resolution, consequence: DcRoll, before: Sequence[Fact], rolled: rolls.Rolled
) -> list[Fact]:
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*before, rolled.fact, *_fold(ctx, branch)]


def _rested(ctx: Resolution, rest: RestType) -> Fact:
    refilled = features.recharged(ctx, rest)
    slots = spells.recharged(ctx, rest)
    names = [*refilled, *(("spell slots",) if slots else ())]
    recharged = f"; recharged {', '.join(names)}" if names else ""
    trace = f"completed a {rest} rest{recharged}"
    return Fact(
        source=ENGINE_ID,
        kind="rested",
        trace=trace,
        narrator=trace,
        data={"rest": rest, "refilled": list(refilled), "slots": list(slots)},
    )
