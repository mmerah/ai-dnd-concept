from random import Random
from typing import Literal

from ...domain.models import Damage, EntityId, Event, Heal, HpChanged, Magnitude
from ...utils import dice
from .. import rules
from . import common
from .resolution import Resolution


def damage(ctx: Resolution, consequence: Damage) -> list[Event]:
    return hp_events(ctx, consequence.target_id, consequence.amount, sign=-1)


def heal(ctx: Resolution, consequence: Heal) -> list[Event]:
    return hp_events(ctx, consequence.target_id, consequence.amount, sign=+1)


def hp_events(
    ctx: Resolution, target_id: EntityId | None, amount: Magnitude, *, sign: Literal[1, -1]
) -> list[Event]:
    target = ctx.target(target_id)
    total, rolls = _magnitude(amount, ctx.rng)
    after = target.stats.with_hp_delta(sign * total)
    delta = after.hp - target.stats.hp
    events: list[Event] = [*common.reveal(target), *rolls]
    if delta == 0:
        return events
    changed = HpChanged(
        target_id=target.id, target_name=target.name, delta=delta, wounds=after.wounds
    )
    return [*events, changed]


def _magnitude(amount: Magnitude, rng: Random) -> tuple[int, list[Event]]:
    if isinstance(amount, int):
        return amount, []
    total, rolled = rules.roll_dice(amount, rng)
    return total, [] if dice.is_constant(amount) else [rolled]
