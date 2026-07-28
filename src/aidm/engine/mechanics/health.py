"""Hit points, and the one clamp damage and healing both go through."""

from random import Random
from typing import Literal

from ...domain.models import EntityId, Event, HpChanged, Magnitude
from ...utils import dice
from .. import rules
from . import common
from .resolution import Resolution


def damage(ctx: Resolution, target_id: EntityId | None, amount: Magnitude) -> list[Event]:
    return hp_events(ctx, target_id, amount, sign=-1)


def heal(ctx: Resolution, target_id: EntityId | None, amount: Magnitude) -> list[Event]:
    return hp_events(ctx, target_id, amount, sign=+1)


def hp_events(
    ctx: Resolution, target_id: EntityId | None, amount: Magnitude, *, sign: Literal[1, -1]
) -> list[Event]:
    """Shared with `combat`, so the clamp and the zero-delta rule cannot diverge between a blow
    and a trap."""
    target = ctx.target(target_id)
    total, rolls = _magnitude(amount, ctx.rng)
    # `with_hp_delta` stays the one clamp, here as much as in the reducer.
    after = target.stats.with_hp_delta(sign * total)
    delta = after.hp - target.stats.hp
    events: list[Event] = [*common.reveal(target), *rolls]
    # A change the clamp swallows whole is not an event: no hit point moved, so none is reported.
    if delta == 0:
        return events
    changed = HpChanged(
        target_id=target.id, target_name=target.name, delta=delta, wounds=after.wounds
    )
    return [*events, changed]


def _magnitude(amount: Magnitude, rng: Random) -> tuple[int, list[Event]]:
    """The roll is folded into the change that spends it: dice fall here, so the Narrator gets the
    die as evidence with no value flowing between consequences. A constant carries no die however
    it is written, so `4` and `'4'` reach the Narrator identically."""
    if isinstance(amount, int):
        return amount, []
    total, rolled = rules.roll_dice(amount, rng)
    return total, [] if dice.is_constant(amount) else [rolled]
