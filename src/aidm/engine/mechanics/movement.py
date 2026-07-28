"""Actors moving between locations."""

from ...domain.models import ActorEntity, EntityId, Event, LocationEntity, Moved
from . import common
from .resolution import Resolution


def move(ctx: Resolution, location_id: EntityId, actor_id: EntityId | None) -> list[Event]:
    """Another actor's move must touch the player's location, so the summary never narrates
    movement the player could not witness; arriving where the player is also reveals them."""
    dest = ctx.of_kind(location_id, LocationEntity)
    player = ctx.player
    if actor_id is None or actor_id == player.id:  # arriving somewhere hidden reveals it
        return [*common.reveal(dest), _moved(player, dest)]
    actor = ctx.of_kind(actor_id, ActorEntity)
    if actor.location_id != player.location_id and dest.id != player.location_id:
        raise ValueError(f"cannot move {actor_id!r}: the player would not witness it")
    reveal = common.reveal(actor) if dest.id == player.location_id else []
    return [*reveal, _moved(actor, dest)]


def _moved(actor: ActorEntity, dest: LocationEntity) -> Moved:
    return Moved(
        actor_id=actor.id, actor_name=actor.name, location_id=dest.id, location_name=dest.name
    )
