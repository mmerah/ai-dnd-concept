from random import Random
from typing import Literal

from aidm.base import PLAYER_ID, EntityId
from aidm.facts import Fact

from .. import dice, rolls
from ..access import Dnd5eWorld
from ..dice import Magnitude
from ..identity import ENGINE_ID
from ..state import Dnd5eActor
from . import common


def hp_facts(
    world: Dnd5eWorld, target_id: EntityId | None, amount: Magnitude, *, sign: Literal[1, -1]
) -> list[Fact]:
    target = world.target(target_id)
    total, rolled = _magnitude(amount, world.rng)
    facts: list[Fact] = [*common.reveal(world, target), *rolled]
    delta = target.stats.apply_hp_delta(sign * total)
    if delta == 0:
        return facts
    return [*facts, _hp_changed(target, delta)]


def _hp_changed(target: Dnd5eActor, delta: int) -> Fact:
    wounds = target.stats.wounds
    trace = f"hp {delta:+d}" if target.id == PLAYER_ID else f"{target.name} is {wounds}"
    return Fact(
        source=ENGINE_ID,
        kind="hp_changed",
        trace=trace,
        narrator=trace,
        data={
            "target_id": target.id,
            "target_name": target.name,
            "delta": delta,
            "wounds": wounds,
        },
    )


def _magnitude(amount: Magnitude, rng: Random) -> tuple[int, list[Fact]]:
    if isinstance(amount, int):
        return amount, []
    total, rolled = rolls.roll_dice(amount, rng)
    return total, [] if dice.is_constant(amount) else [rolled]
