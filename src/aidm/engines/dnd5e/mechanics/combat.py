from aidm.facts import Fact

from .. import procedures
from ..direction import Attack
from . import common, health
from .resolution import Resolution


def attack(ctx: Resolution, consequence: Attack) -> list[Fact]:
    """Emit the roll even on a miss because it is Narrator evidence."""
    attacker = ctx.target(consequence.attacker_id)
    target = ctx.target(consequence.target_id)
    if attacker.id == target.id:
        raise ValueError(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(ctx.world, attacker, consequence.weapon, ctx.ruleset)
    struck = procedures.strike(attacker, target, swung, ctx.rng)
    seen: list[Fact] = [*common.reveal(ctx, attacker), *common.reveal(ctx, target), struck.fact]
    if not struck.hit or swung.damage is None:
        return seen
    return [*seen, *health.hp_facts(ctx, target.id, swung.damage, sign=-1)]
