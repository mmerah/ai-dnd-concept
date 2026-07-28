from ...domain.models import Entity, EntityDiscovered, Event


def reveal(entity: Entity) -> list[Event]:
    """Reveal hidden entities before an event names them."""
    return [] if entity.known else [EntityDiscovered(entity_id=entity.id, name=entity.name)]
