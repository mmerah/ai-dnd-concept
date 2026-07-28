"""Director mechanics -> events. Pure: no LLM, no I/O; takes the consequence list only, so
`engine/` stays blind to intent/tone/speaker.

Routing and the fold: each mechanic lives in its own module under `mechanics/`, and the `match`
below stays exhaustive so a new consequence is a build error here rather than a silently unhandled
one. The two rolls are resolved here rather than in a slice because resolving one *is* folding the
branch it selected, and that recursion runs over the whole vocabulary."""

from collections.abc import Sequence
from random import Random

from ..domain.models import (
    ApplyCondition,
    Attack,
    Consequence,
    Damage,
    DcRoll,
    DcRolled,
    Discover,
    DropItem,
    Event,
    GainImprovisedItem,
    GameState,
    GiveItem,
    Heal,
    Move,
    RollCheck,
    RollSave,
    TakeItem,
)
from . import rules
from .mechanics import combat, common, conditions, health, inventory, movement
from .mechanics.resolution import Resolution
from .ruleset import Ruleset


def resolve(
    mechanics: Sequence[Consequence], state: GameState, rng: Random, ruleset: Ruleset
) -> list[Event]:
    return _fold(Resolution(state=state, rng=rng, ruleset=ruleset), mechanics)


def _fold(ctx: Resolution, mechanics: Sequence[Consequence]) -> list[Event]:
    """Fold left to right, so each consequence sees the state its predecessors produced."""
    events: list[Event] = []
    for consequence in mechanics:
        new = _walk(ctx, consequence)
        events.extend(new)
        ctx = ctx.then(new)
    return events


def _walk(ctx: Resolution, consequence: Consequence) -> list[Event]:
    """Each slice's guards fail fast on a broken plan; the Director's validator catches most of them
    first, as a retry."""
    match consequence:
        case RollCheck(ability=ability, dc=dc):
            rolled = rules.roll_check(ctx.player, ability, dc, ctx.rng)
            return _branched(ctx, consequence, (), rolled)
        case RollSave(ability=ability, dc=dc, target_id=target_id):
            # Unlike a check, a save may be rolled by someone the player has not met.
            target = ctx.target(target_id)
            rolled = rules.roll_save(target, ability, dc, ctx.rng)
            return _branched(ctx, consequence, common.reveal(target), rolled)
        case Attack(weapon=weapon, target_id=target_id, attacker_id=attacker_id):
            return combat.attack(ctx, attacker_id, target_id, weapon)
        case Damage(amount=amount, target_id=target_id):
            return health.damage(ctx, target_id, amount)
        case Heal(amount=amount, target_id=target_id):
            return health.heal(ctx, target_id, amount)
        case ApplyCondition(condition=condition, ends=ends, target_id=target_id):
            return conditions.change(ctx, target_id, condition, active=not ends)
        case Discover(entity_id=entity_id):
            return common.reveal(ctx.entity(entity_id))  # re-discovery is a no-op, not an error
        case Move(location_id=location_id, actor_id=actor_id):
            return movement.move(ctx, location_id, actor_id)
        case TakeItem(item_id=item_id):
            return inventory.take(ctx, item_id)
        case DropItem(item_id=item_id):
            return inventory.drop(ctx, item_id)
        case GiveItem(item_id=item_id, actor_id=actor_id):
            return inventory.give(ctx, item_id, actor_id)
        case GainImprovisedItem(item_name=item_name):
            return inventory.improvise(ctx, item_name)


def _branched(
    ctx: Resolution, consequence: DcRoll, before: Sequence[Event], rolled: DcRolled
) -> list[Event]:
    """The roll and whatever preceded it, then only the branch the roll selected. The branch folds
    against the state *all* of them produced, so a reveal already emitted is not emitted twice."""
    emitted = [*before, rolled]
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*emitted, *_fold(ctx.then(emitted), branch)]
