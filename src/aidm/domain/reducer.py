"""The single pure reducer plus the player-visible projection. Nothing else produces state."""

from collections.abc import Sequence
from functools import reduce

from .models import (
    PLAYER_ID,
    CheckRolled,
    DiceRolled,
    Entity,
    EntityCreated,
    EntityDiscovered,
    EntityId,
    Event,
    GameState,
    HpChanged,
    ItemEntity,
    ItemMoved,
    LocationEntity,
    Moved,
    NpcEntity,
    find,
    updated,
)


def _with_entities(state: GameState, entities: dict[EntityId, Entity]) -> GameState:
    return updated(state, world=updated(state.world, entities=entities))


def _move_actor(state: GameState, subject_id: EntityId, location_id: EntityId) -> GameState:
    if not isinstance(find(state.world.entities, location_id), LocationEntity):
        raise ValueError(f"cannot move to {location_id!r}: not a location")
    if subject_id == PLAYER_ID:
        return updated(state, character=updated(state.character, location_id=location_id))
    npc = find(state.world.entities, subject_id)
    if not isinstance(npc, NpcEntity):
        raise ValueError(f"cannot move {subject_id!r}: not an npc")
    moved = updated(npc, location_id=location_id)
    return _with_entities(state, {**state.world.entities, subject_id: moved})


def _move_item(state: GameState, item_id: EntityId, to_id: EntityId, to_kind: str) -> GameState:
    entities = dict(state.world.entities)
    item = entities.get(item_id)
    if not isinstance(item, ItemEntity):
        raise ValueError(f"cannot move {item_id!r}: not a canon item")
    # Lift the item out of wherever it rests — the player's inventory or any npc's — before placing
    # it, so the held-xor-located invariant holds after every move.
    inventory = [i for i in state.character.inventory if i != item_id]
    for holder_id, holder in list(entities.items()):
        if isinstance(holder, NpcEntity) and item_id in holder.inventory:
            kept = [i for i in holder.inventory if i != item_id]
            entities[holder_id] = updated(holder, inventory=kept)
    match to_kind:
        case "player":
            inventory.append(item_id)
            entities[item_id] = updated(item, location_id=None)
        case "npc":
            recipient = entities.get(to_id)
            if not isinstance(recipient, NpcEntity):
                raise ValueError(f"cannot give to {to_id!r}: not an npc")
            entities[to_id] = updated(recipient, inventory=[*recipient.inventory, item_id])
            entities[item_id] = updated(item, location_id=None)
        case _:  # "location"
            if not isinstance(entities.get(to_id), LocationEntity):
                raise ValueError(f"cannot drop at {to_id!r}: not a location")
            entities[item_id] = updated(item, location_id=to_id)
    character = updated(state.character, inventory=inventory)
    return updated(state, character=character, world=updated(state.world, entities=entities))


def _apply_one(state: GameState, event: Event) -> GameState:
    match event:
        case CheckRolled() | DiceRolled():  # evidence for the Narrator; consequences are separate
            return state
        case ItemMoved(item_id=item_id, to_id=to_id, to_kind=to_kind):
            return _move_item(state, item_id, to_id, to_kind)
        case HpChanged(delta=delta):
            hp = max(0, min(state.character.max_hp, state.character.hp + delta))
            return updated(state, character=updated(state.character, hp=hp))
        case Moved(subject_id=subject_id, location_id=location_id):
            return _move_actor(state, subject_id, location_id)
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
