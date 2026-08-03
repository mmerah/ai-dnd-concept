from aidm.base import PLAYER_ID
from aidm.content import Rules
from aidm.world import EngineRecords, GameState

from .state import StoryActorState, StoryItemState


def actor_state(rules: Rules) -> StoryActorState:
    return StoryActorState.model_validate(rules)


def item_state(rules: Rules) -> StoryItemState:
    return StoryItemState.model_validate(rules)


def player_state(state: GameState) -> StoryActorState:
    """A detached read for reporting only; mutating it does nothing until a `StoryWorld` flushes."""
    return actor_state(state.world.record(PLAYER_ID, "actor").rules)


class StoryWorld(EngineRecords[StoryActorState, StoryItemState]):
    def __init__(self, state: GameState) -> None:
        super().__init__(state, StoryActorState, StoryItemState)
