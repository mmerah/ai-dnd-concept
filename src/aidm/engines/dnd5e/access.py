from aidm.base import PLAYER_ID, EntityId
from aidm.content import Rules
from aidm.world import EngineRecords, GameState

from .state import Dnd5eActor, Dnd5eActorState, Dnd5eItem, Dnd5eItemState


def actor_state(rules: Rules) -> Dnd5eActorState:
    return Dnd5eActorState.model_validate(rules)


def item_state(rules: Rules) -> Dnd5eItemState:
    return Dnd5eItemState.model_validate(rules)


class Dnd5eWorld:
    def __init__(self, state: GameState) -> None:
        self._records = EngineRecords(state, Dnd5eActorState, Dnd5eItemState)

    @property
    def state(self) -> GameState:
        return self._records.state

    def actor(self, actor_id: EntityId) -> Dnd5eActor:
        entity, state = self._records.actor(actor_id)
        return Dnd5eActor(entity=entity, state=state)

    def item(self, item_id: EntityId) -> Dnd5eItem:
        entity, state = self._records.item(item_id)
        return Dnd5eItem(entity=entity, state=state)

    def player(self) -> Dnd5eActor:
        return self.actor(PLAYER_ID)

    def actors(self) -> tuple[Dnd5eActor, ...]:
        return tuple(self.actor(actor_id) for actor_id in self.state.world.actors)

    def items(self) -> tuple[Dnd5eItem, ...]:
        return tuple(self.item(item_id) for item_id in self.state.world.items)

    def carried_by(self, actor_id: EntityId) -> tuple[Dnd5eItem, ...]:
        return tuple(
            self.item(record.entity.id) for record in self.state.world.carried_by(actor_id)
        )

    def commit(self) -> GameState:
        return self._records.commit()
