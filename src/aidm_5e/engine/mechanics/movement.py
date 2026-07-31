from aidm.domain.entities import ActorEntity, LocationEntity

from ...domain.models.consequences import Move
from ...domain.models.facts import Emitted
from . import common
from .resolution import Resolution


def move(ctx: Resolution, consequence: Move) -> list[Emitted]:
    """Reject NPC movement the player could not witness."""
    dest = ctx.of_kind(consequence.location_id, LocationEntity)
    player = ctx.player
    actor_id = consequence.actor_id
    if actor_id is None or actor_id == player.id:
        seen: list[Emitted] = [*common.reveal(ctx, dest)]
        return [*seen, ctx.draft.move_actor(player.entity, dest)]
    actor = ctx.of_kind(actor_id, ActorEntity)
    if actor.location_id != player.location_id and dest.id != player.location_id:
        raise ValueError(f"cannot move {actor_id!r}: the player would not witness it")
    revealed: list[Emitted] = [*common.reveal(ctx, actor)] if dest.id == player.location_id else []
    return [*revealed, ctx.draft.move_actor(actor, dest)]
