from collections.abc import Sequence
from random import Random

from aidm.actions import is_world_action, resolve_world_action
from aidm.base import Entity, ItemEntity
from aidm.world import EntityRules, GameState

from . import features, progression, rolls, spells
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
from .facts import DcRolled, Emitted, Rested
from .mechanics import combat, common, conditions, health
from .mechanics.resolution import Resolution
from .ruleset import Ruleset
from .state import Dnd5eItemState


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
    if is_world_action(consequence):
        return list(resolve_world_action(consequence, ctx.draft, _default_rules))
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
        case _:
            raise TypeError(f"unsupported 5e consequence {type(consequence).__name__}")


def _default_rules(entity: Entity) -> EntityRules | None:
    if not isinstance(entity, ItemEntity):
        raise TypeError(f"5e cannot improvise a {entity.kind}")
    return Dnd5eItemState()


def _branched(
    ctx: Resolution, consequence: DcRoll, before: Sequence[Emitted], rolled: DcRolled
) -> list[Emitted]:
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*before, rolled, *_fold(ctx, branch)]
