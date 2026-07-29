from collections.abc import Sequence
from random import Random

from ..domain.models.consequences import (
    ApplyCondition,
    Attack,
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
from ..domain.models.events import DcRolled, Event
from ..domain.models.state import GameState
from . import features, progression, rules
from .mechanics import combat, common, conditions, health, inventory, movement
from .mechanics.resolution import Resolution
from .ruleset import Ruleset


def resolve(
    mechanics: Sequence[Consequence], state: GameState, rng: Random, ruleset: Ruleset
) -> list[Event]:
    return _fold(Resolution(state=state, rng=rng, ruleset=ruleset), mechanics)


def _fold(ctx: Resolution, mechanics: Sequence[Consequence]) -> list[Event]:
    events: list[Event] = []
    for consequence in mechanics:
        new = _walk(ctx, consequence)
        events.extend(new)
        ctx = ctx.then(new)
    return events


def _walk(ctx: Resolution, consequence: Consequence) -> list[Event]:
    match consequence:
        case RollCheck(ability=ability, dc=dc):
            rolled = rules.roll_check(ctx.player, ability, dc, ctx.rng)
            return _branched(ctx, consequence, (), rolled)
        case RollSave(ability=ability, dc=dc, target_id=target_id):
            target = ctx.target(target_id)
            rolled = rules.roll_save(target, ability, dc, ctx.rng)
            return _branched(ctx, consequence, common.reveal(target), rolled)
        case Attack():
            return combat.attack(ctx, consequence)
        case LevelUp():
            return progression.offer(ctx.player)
        case UseFeature():
            return features.use(ctx, consequence)
        case Rest():
            return features.rest(ctx, consequence)
        case Damage():
            return health.damage(ctx, consequence)
        case Heal():
            return health.heal(ctx, consequence)
        case ApplyCondition():
            return conditions.change(ctx, consequence)
        case Discover():
            return common.reveal(ctx.entity(consequence.entity_id))
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
    ctx: Resolution, consequence: DcRoll, before: Sequence[Event], rolled: DcRolled
) -> list[Event]:
    emitted = [*before, rolled]
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*emitted, *_fold(ctx.then(emitted), branch)]
