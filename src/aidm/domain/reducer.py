"""The single pure reducer plus the player-visible projection. Nothing else produces state."""

from collections.abc import Sequence
from functools import reduce

from .models import (
    CheckRolled,
    Entity,
    EntityCreated,
    EntityDiscovered,
    EntityId,
    Event,
    GameState,
    HpChanged,
    InventoryChanged,
    Moved,
    find,
    updated,
)


def _with_entities(state: GameState, entities: dict[EntityId, Entity]) -> GameState:
    return updated(state, world=updated(state.world, entities=entities))


def _apply_one(state: GameState, event: Event) -> GameState:
    match event:
        case CheckRolled():  # evidence for the Narrator; the consequences are separate events
            return state
        case InventoryChanged(item=item, delta=delta):
            inventory = list(state.character.inventory)
            if delta > 0:
                inventory.append(item)
            elif item in inventory:
                inventory.remove(item)
            else:
                raise ValueError(f"cannot lose {item!r}: not in inventory")
            return updated(state, character=updated(state.character, inventory=inventory))
        case HpChanged(delta=delta):
            hp = max(0, min(state.character.max_hp, state.character.hp + delta))
            return updated(state, character=updated(state.character, hp=hp))
        case Moved(entity_id=entity_id):
            if find(state.world.entities, entity_id) is None:
                raise ValueError(f"cannot move to unknown entity {entity_id!r}")
            return updated(state, character=updated(state.character, location_id=entity_id))
        case EntityDiscovered(entity_id=entity_id):
            entity = find(state.world.entities, entity_id)
            if entity is None:
                raise ValueError(f"cannot discover unknown entity {entity_id!r}")
            revealed = {**state.world.entities, entity_id: updated(entity, known=True)}
            return _with_entities(state, revealed)
        case EntityCreated(entity=entity):
            # A duplicate id is a broken invariant (hard fail here); a duplicate name is a
            # judgement call screened before creation in engine/growth.py.
            if entity.id in state.world.entities:
                raise ValueError(f"entity id {entity.id!r} already exists")
            return _with_entities(state, {**state.world.entities, entity.id: entity})


def apply(state: GameState, events: Sequence[Event]) -> GameState:
    """Pure: never mutates `state`."""
    return reduce(_apply_one, events, state)


def render(events: Sequence[Event]) -> str:
    """Player-visible event summaries — the Narrator's only source of truth."""
    return "\n".join(f"- {e.summary}" for e in events) or "- (nothing mechanical happened)"
