from random import Random
from typing import Literal

from aidm.base import EntityId

from .. import dice, rolls
from ..direction import Damage, Heal, Magnitude
from ..facts import Emitted, HpChanged
from . import common
from .resolution import Resolution


def damage(ctx: Resolution, consequence: Damage) -> list[Emitted]:
    return hp_facts(ctx, consequence.target_id, consequence.amount, sign=-1)


def heal(ctx: Resolution, consequence: Heal) -> list[Emitted]:
    return hp_facts(ctx, consequence.target_id, consequence.amount, sign=+1)


def hp_facts(
    ctx: Resolution, target_id: EntityId | None, amount: Magnitude, *, sign: Literal[1, -1]
) -> list[Emitted]:
    target = ctx.target(target_id)
    total, rolled = _magnitude(amount, ctx.rng)
    facts: list[Emitted] = [*common.reveal(ctx, target), *rolled]
    delta = target.stats.apply_hp_delta(sign * total)
    if delta == 0:
        return facts
    changed = HpChanged(
        target_id=target.id, target_name=target.name, delta=delta, wounds=target.stats.wounds
    )
    return [*facts, changed]


def _magnitude(amount: Magnitude, rng: Random) -> tuple[int, list[Emitted]]:
    if isinstance(amount, int):
        return amount, []
    total, rolled = rolls.roll_dice(amount, rng)
    return total, [] if dice.is_constant(amount) else [rolled]
