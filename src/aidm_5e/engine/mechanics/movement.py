from aidm.domain.entities import ActorEntity, LocationEntity
from aidm.domain.events import ActorMoved

from ...domain.models.consequences import Move
from ...domain.models.events import Dnd5eEvent
from . import common
from .resolution import Resolution


def move(ctx: Resolution, consequence: Move) -> list[Dnd5eEvent]:
    """Reject NPC movement the player could not witness."""
    dest = ctx.of_kind(consequence.location_id, LocationEntity)
    player = ctx.player
    actor_id = consequence.actor_id
    if actor_id is None or actor_id == player.id:
        return [*common.reveal(dest), _moved(player.entity, dest)]
    actor = ctx.of_kind(actor_id, ActorEntity)
    if actor.location_id != player.location_id and dest.id != player.location_id:
        raise ValueError(f"cannot move {actor_id!r}: the player would not witness it")
    reveal = common.reveal(actor) if dest.id == player.location_id else []
    return [*reveal, _moved(actor, dest)]


def _moved(actor: ActorEntity, dest: LocationEntity) -> ActorMoved:
    return ActorMoved(
        actor_id=actor.id, actor_name=actor.name, location_id=dest.id, location_name=dest.name
    )
