"""Attacks."""

from ...domain.models import EntityId, Event
from .. import procedures
from . import common, health
from .resolution import Resolution


def attack(
    ctx: Resolution, attacker_id: EntityId | None, target_id: EntityId | None, weapon: str
) -> list[Event]:
    """A miss is still evidence, so the roll is emitted either way."""
    attacker, target = ctx.target(attacker_id), ctx.target(target_id)
    if attacker.id == target.id:
        raise ValueError(f"cannot attack {target.id!r}: an actor does not strike at themselves")
    swung = procedures.swing(ctx.state, attacker, weapon, ctx.library)
    rolled = procedures.strike(attacker, target, swung, ctx.rng)
    seen: list[Event] = [*common.reveal(attacker), *common.reveal(target), rolled]
    if not rolled.hit or swung.damage is None:
        return seen
    return [*seen, *health.hp_events(ctx.then(seen), target.id, swung.damage, sign=-1)]
