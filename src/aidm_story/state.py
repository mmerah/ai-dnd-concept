from aidm.domain.entities import ActorEntity, Entity, ItemEntity
from aidm.domain.state import GameState

from .models import DEFAULT_APPROACHES, StoryActorState, StoryItemState, StoryState


def story_state(state: GameState) -> StoryState:
    if not isinstance(state.engine, StoryState):
        raise ValueError(f"Story received a {state.engine_id!r} state")
    return state.engine


def created_state(state: GameState, entity: Entity) -> StoryState:
    """A newly narrated entity starts unremarkable: baseline approaches, no gear benefit."""
    engine = story_state(state)
    match entity:
        case ActorEntity():
            return engine.with_actor(entity.id, StoryActorState(approaches=DEFAULT_APPROACHES))
        case ItemEntity():
            return engine.with_item(entity.id, StoryItemState())
        case _:
            return engine
