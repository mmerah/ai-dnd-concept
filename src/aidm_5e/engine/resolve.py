from collections.abc import Sequence
from random import Random

from aidm.domain.state import GameState

from ..domain.models.consequences import (
    ApplyCondition,
    Attack,
    Cast,
    Consequence,
    Damage,
    DcRoll,
    Discover,
    DropItem,
    GainImprovisedItem,
    GiveItem,
    Heal,
    LevelUp,
    Move,
    Rest,
    RollCheck,
    RollSave,
    TakeItem,
    UseFeature,
)
from ..domain.models.facts import DcRolled, Emitted, Rested
from . import features, progression, rules, spells
from .mechanics import combat, common, conditions, health, inventory, movement
from .mechanics.resolution import Resolution
from .ruleset import Ruleset


def resolve(
    mechanics: Sequence[Consequence], draft: GameState, rng: Random, ruleset: Ruleset
) -> list[Emitted]:
    return _fold(Resolution(draft=draft, rng=rng, ruleset=ruleset), mechanics)


def _fold(ctx: Resolution, mechanics: Sequence[Consequence]) -> list[Emitted]:
    facts: list[Emitted] = []
    for consequence in mechanics:
        facts.extend(_walk(ctx, consequence))
    return facts


def _walk(ctx: Resolution, consequence: Consequence) -> list[Emitted]:
    match consequence:
        case RollCheck(ability=ability, dc=dc):
            rolled = rules.roll_check(ctx.player, ability, dc, ctx.rng)
            return _branched(ctx, consequence, (), rolled)
        case RollSave(ability=ability, dc=dc, target_id=target_id):
            target = ctx.target(target_id)
            rolled = rules.roll_save(target, ability, dc, ctx.rng)
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
            return [
                Rested(
                    rest=rest,
                    refilled=features.recharged(ctx, rest),
                    slots=spells.recharged(ctx, rest),
                )
            ]
        case Damage():
            return health.damage(ctx, consequence)
        case Heal():
            return health.heal(ctx, consequence)
        case ApplyCondition():
            return conditions.change(ctx, consequence)
        case Discover():
            return [*common.reveal(ctx, ctx.entity(consequence.entity_id))]
        case Move():
            return movement.move(ctx, consequence)
        case TakeItem():
            return inventory.take(ctx, consequence)
        case DropItem():
            return inventory.drop(ctx, consequence)
        case GiveItem():
            return inventory.give(ctx, consequence)
        case GainImprovisedItem():
            return inventory.improvise(ctx, consequence)


def _branched(
    ctx: Resolution, consequence: DcRoll, before: Sequence[Emitted], rolled: DcRolled
) -> list[Emitted]:
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*before, rolled, *_fold(ctx, branch)]
