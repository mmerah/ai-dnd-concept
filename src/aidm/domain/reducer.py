"""The single pure reducer plus the player-visible projection. Nothing else produces state."""

from collections.abc import Sequence
from functools import reduce

from .models import (
    ActorEntity,
    CheckRolled,
    ConditionChanged,
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
    find,
    updated,
)


def _with_entities(state: GameState, entities: dict[EntityId, Entity]) -> GameState:
    return updated(state, world=updated(state.world, entities=entities))


def _actor(state: GameState, entity_id: EntityId, verb: str) -> ActorEntity:
    actor = find(state.world.entities, entity_id)
    if not isinstance(actor, ActorEntity):
        raise ValueError(f"cannot {verb} {entity_id!r}: not an actor")
    return actor


def _move_actor(state: GameState, actor_id: EntityId, location_id: EntityId) -> GameState:
    if not isinstance(find(state.world.entities, location_id), LocationEntity):
        raise ValueError(f"cannot move to {location_id!r}: not a location")
    moved = updated(_actor(state, actor_id, "move"), location_id=location_id)
    return _with_entities(state, {**state.world.entities, actor_id: moved})


def _move_item(state: GameState, item_id: EntityId, to_id: EntityId) -> GameState:
    entities = dict(state.world.entities)
    item = entities.get(item_id)
    if not isinstance(item, ItemEntity):
        raise ValueError(f"cannot move {item_id!r}: not a canon item")
    # Lift the item out of whichever inventory holds it before placing it, so the held-xor-located
    # invariant holds after every move.
    for holder_id, holder in list(entities.items()):
        if isinstance(holder, ActorEntity) and item_id in holder.inventory:
            kept = [i for i in holder.inventory if i != item_id]
            entities[holder_id] = updated(holder, inventory=kept)
    match entities.get(to_id):
        case LocationEntity():
            entities[item_id] = updated(item, location_id=to_id)
        case ActorEntity(inventory=inventory):
            entities[to_id] = updated(entities[to_id], inventory=[*inventory, item_id])
            entities[item_id] = updated(item, location_id=None)
        case _:
            raise ValueError(f"cannot move {item_id!r} to {to_id!r}: it holds nothing")
    return _with_entities(state, entities)


def _apply_one(state: GameState, event: Event) -> GameState:
    match event:
        case CheckRolled() | DiceRolled():  # evidence for the Narrator; consequences are separate
            return state
        case ItemMoved(item_id=item_id, to_id=to_id):
            return _move_item(state, item_id, to_id)
        case HpChanged(target_id=target_id, delta=delta):
            actor = _actor(state, target_id, "change the hit points of")
            hurt = updated(actor, stats=actor.stats.with_hp_delta(delta))
            return _with_entities(state, {**state.world.entities, target_id: hurt})
        case ConditionChanged(target_id=target_id, condition=condition, active=active):
            actor = _actor(state, target_id, "change the condition of")
            stats = actor.stats.with_condition(condition, active=active)
            under = updated(actor, stats=stats)
            return _with_entities(state, {**state.world.entities, target_id: under})
        case Moved(actor_id=actor_id, location_id=location_id):
            return _move_actor(state, actor_id, location_id)
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
    """Player-visible event summaries — the Narrator's only source of truth, and the whole of what
    it is ever shown about this turn's mechanics."""
    return "\n".join(f"- {e.summary}" for e in events) or "- (nothing mechanical happened)"
