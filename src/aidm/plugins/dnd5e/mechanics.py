from random import Random
from typing import Literal

from pydantic_ai import ModelRetry

from aidm.kernel.base import PLAYER_ID, Entity, EntityId
from aidm.kernel.facts import Fact

from . import dice, procedures, rolls
from .access import Dnd5eWorld
from .content.vocabulary import ConditionName
from .dice import Magnitude
from .identity import ENGINE_ID
from .state import Dnd5eActor, Dnd5eItem


def reveal(world: Dnd5eWorld, target: Entity | Dnd5eActor | Dnd5eItem) -> list[Fact]:
    entity = target if isinstance(target, Entity) else target.entity
    return world.state.reveal(entity)


def attack(
    world: Dnd5eWorld, weapon: str, target_id: EntityId | None, attacker_id: EntityId | None
) -> list[Fact]:
    attacker = world.target(attacker_id)
    target = world.target(target_id)
    if attacker.id == target.id:
        raise ModelRetry(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(world, attacker, weapon, world.ruleset)
    struck = procedures.strike(attacker, target, swung, world.rng)
    seen: list[Fact] = [*reveal(world, attacker), *reveal(world, target), struck.fact]
    if not struck.hit or swung.damage is None:
        return seen
    return [*seen, *hp_facts(world, target.id, swung.damage, sign=-1)]


def hp_facts(
    world: Dnd5eWorld, target_id: EntityId | None, amount: Magnitude, *, sign: Literal[1, -1]
) -> list[Fact]:
    target = world.target(target_id)
    total, rolled = _magnitude(amount, world.rng)
    facts: list[Fact] = [*reveal(world, target), *rolled]
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


def change_condition(
    world: Dnd5eWorld, target_id: EntityId | None, condition: ConditionName, *, ends: bool
) -> list[Fact]:
    target = world.target(target_id)
    active = not ends
    seen: list[Fact] = [*reveal(world, target)]
    if not target.stats.apply_condition(condition, active=active):
        return seen
    return [*seen, _condition_changed(target, condition, active=active)]


def _condition_changed(target: Dnd5eActor, condition: ConditionName, *, active: bool) -> Fact:
    who = "the player" if target.id == PLAYER_ID else target.name
    held = "is" if active else "is no longer"
    trace = f"{who} {held} {condition}"
    return Fact(
        source=ENGINE_ID,
        kind="condition_changed",
        trace=trace,
        narrator=trace,
        data={
            "target_id": target.id,
            "target_name": target.name,
            "condition": condition,
            "active": active,
        },
    )
