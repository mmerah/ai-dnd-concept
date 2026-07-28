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
        case Attack():
            return combat.attack(ctx, consequence)
        case Damage():
            return health.damage(ctx, consequence)
        case Heal():
            return health.heal(ctx, consequence)
        case ApplyCondition():
            return conditions.change(ctx, consequence)
        case Discover():  # re-discovery is a no-op, not an error
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
    """The roll and whatever preceded it, then only the branch the roll selected. The branch folds
    against the state *all* of them produced, so a reveal already emitted is not emitted twice."""
    emitted = [*before, rolled]
    branch = consequence.on_success if rolled.success else consequence.on_failure
    return [*emitted, *_fold(ctx.then(emitted), branch)]
