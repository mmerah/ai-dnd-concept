"""What every mechanic owes the player."""

from ...domain.models import Entity, EntityDiscovered, Event


def reveal(entity: Entity) -> list[Event]:
    """Reaching, taking or harming a hidden thing is learning of it: the events a mechanic emits
    name the entity, so the player must be told of it first."""
    return [] if entity.known else [EntityDiscovered(entity_id=entity.id, name=entity.name)]
