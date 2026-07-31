from ...domain.models.consequences import Attack
from ...domain.models.facts import Emitted
from .. import procedures
from . import common, health
from .resolution import Resolution


def attack(ctx: Resolution, consequence: Attack) -> list[Emitted]:
    """Emit the roll even on a miss because it is Narrator evidence."""
    attacker = ctx.target(consequence.attacker_id)
    target = ctx.target(consequence.target_id)
    if attacker.id == target.id:
        raise ValueError(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(ctx.draft, attacker, consequence.weapon, ctx.ruleset)
    rolled = procedures.strike(attacker, target, swung, ctx.rng)
    seen: list[Emitted] = [*common.reveal(ctx, attacker), *common.reveal(ctx, target), rolled]
    if not rolled.hit or swung.damage is None:
        return seen
    return [*seen, *health.hp_facts(ctx, target.id, swung.damage, sign=-1)]
