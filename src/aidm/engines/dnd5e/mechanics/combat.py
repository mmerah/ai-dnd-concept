from pydantic_ai import ModelRetry

from aidm.base import EntityId
from aidm.facts import Fact

from .. import procedures
from ..access import Dnd5eWorld
from . import common, health


def attack(
    world: Dnd5eWorld, weapon: str, target_id: EntityId | None, attacker_id: EntityId | None
) -> list[Fact]:
    attacker = world.target(attacker_id)
    target = world.target(target_id)
    if attacker.id == target.id:
        raise ModelRetry(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(world, attacker, weapon, world.ruleset)
    struck = procedures.strike(attacker, target, swung, world.rng)
    seen: list[Fact] = [*common.reveal(world, attacker), *common.reveal(world, target), struck.fact]
    if not struck.hit or swung.damage is None:
        return seen
    return [*seen, *health.hp_facts(world, target.id, swung.damage, sign=-1)]
