import re

from aidm.state.base import Entity
from aidm.state.world import GameState


def tag_key(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def carriers(state: GameState, actor: Entity) -> tuple[Entity, ...]:
    """Everything whose tags an actor may draw on."""
    found = [actor, *state.world.children(actor.id, "item")]
    place = state.world.location_of(actor)
    if place is not None:
        found.append(state.world.require(place))
        found.extend(state.world.children(place))
    return tuple(found)
