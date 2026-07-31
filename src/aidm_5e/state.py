from aidm.domain.base import EntityId
from aidm.domain.entities import ActorEntity, Entity, ItemEntity, LocationEntity
from aidm.domain.state import GameState

from .domain.models.stats import StatBlock
from .models import Dnd5eActor, Dnd5eActorState, Dnd5eItem, Dnd5eItemState, Dnd5eState


def dnd5e_state(state: GameState) -> Dnd5eState:
    if not isinstance(state.engine, Dnd5eState):
        raise ValueError(f"5e received a {state.engine_id!r} state")
    return state.engine


def created_state(draft: GameState, entity: Entity) -> None:
    """The mechanics a newly narrated entity starts with: none beyond an empty stat block."""
    engine = dnd5e_state(draft)
    match entity:
        case ActorEntity():
            engine.actors[entity.id] = Dnd5eActorState(stats=StatBlock())
        case ItemEntity():
            engine.items[entity.id] = Dnd5eItemState()
        case LocationEntity():
            return


def actor_of(state: GameState, actor_id: EntityId) -> Dnd5eActor:
    entity = state.world.require_kind(actor_id, ActorEntity)
    return Dnd5eActor(entity=entity, state=dnd5e_state(state).actor(actor_id))


def item_of(state: GameState, item_id: EntityId) -> Dnd5eItem:
    entity = state.world.require_kind(item_id, ItemEntity)
    return Dnd5eItem(entity=entity, state=dnd5e_state(state).item(item_id))


def carried_by(state: GameState, actor_id: EntityId) -> tuple[Dnd5eItem, ...]:
    engine = dnd5e_state(state)
    return tuple(
        Dnd5eItem(entity=entity, state=engine.item(entity.id))
        for entity in state.world.carried_by(actor_id)
    )
