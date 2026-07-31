from aidm.base import ActorEntity, Entity, ItemEntity, LocationEntity
from aidm.world import GameState

from .state import DEFAULT_APPROACHES, StoryActorState, StoryItemState, StoryState


def story_state(state: GameState) -> StoryState:
    if not isinstance(state.engine, StoryState):
        raise ValueError(f"Story received a {state.engine_id!r} state")
    return state.engine


def created_state(draft: GameState, entity: Entity) -> None:
    """Give a newly narrated entity baseline Story state."""
    engine = story_state(draft)
    match entity:
        case ActorEntity():
            engine.actors[entity.id] = StoryActorState(approaches=DEFAULT_APPROACHES)
        case ItemEntity():
            engine.items[entity.id] = StoryItemState()
        case LocationEntity():
            return
