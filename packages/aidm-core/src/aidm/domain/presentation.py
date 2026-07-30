from .base import PLAYER_ID
from .events import ActorMoved, CoreEvent, EntityCreated, EntityDiscovered, ItemMoved


def narrator_core_event(event: CoreEvent) -> str:
    match event:
        case EntityCreated(entity=entity):
            return f"new {entity.kind}: {entity.name}"
        case EntityDiscovered(name=name):
            return f"learned of {name}"
        case ActorMoved(actor_name=actor, location_name=location):
            return f"{actor} moved to {location}"
        case ItemMoved(item_name=item, to_id=to_id) if to_id == PLAYER_ID:
            return f"took {item}"
        case ItemMoved(item_name=item, to_kind="actor", to_name=actor):
            return f"gave {item} to {actor}"
        case ItemMoved(item_name=item, to_name=location):
            return f"left {item} at {location}"


def trace_core_event(event: CoreEvent) -> str:
    return narrator_core_event(event)
