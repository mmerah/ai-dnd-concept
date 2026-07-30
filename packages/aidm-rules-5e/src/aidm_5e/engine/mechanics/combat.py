from ...domain.models.consequences import Attack
from ...domain.models.events import Event
from .. import procedures
from . import common, health
from .resolution import Resolution


def attack(ctx: Resolution, consequence: Attack) -> list[Event]:
    """Emit the roll even on a miss because it is Narrator evidence."""
    attacker = ctx.target(consequence.attacker_id)
    target = ctx.target(consequence.target_id)
    if attacker.id == target.id:
        raise ValueError(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(ctx.state, attacker, consequence.weapon, ctx.ruleset)
    rolled = procedures.strike(attacker, target, swung, ctx.rng)
    seen: list[Event] = [*common.reveal(attacker), *common.reveal(target), rolled]
    if not rolled.hit or swung.damage is None:
        return seen
    return [*seen, *health.hp_events(ctx.then(seen), target.id, swung.damage, sign=-1)]
