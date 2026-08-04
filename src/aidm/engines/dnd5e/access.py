from dataclasses import dataclass
from random import Random

from aidm.core.base import PLAYER_ID, EntityId
from aidm.core.tools import require_actor_here
from aidm.core.world import EngineRules, GameState, rules_of

from .ruleset import Ruleset
from .state import Dnd5eActor, Dnd5eActorState, Dnd5eItem, Dnd5eItemState, Dnd5eState, Progression


def read_actor[R: EngineRules](state: GameState[R], actor_id: EntityId) -> Dnd5eActor:
    record = state.world.record(actor_id, "actor")
    return Dnd5eActor(entity=record.entity, state=rules_of(record, Dnd5eActorState))


def read_item[R: EngineRules](state: GameState[R], item_id: EntityId) -> Dnd5eItem:
    record = state.world.record(item_id, "item")
    return Dnd5eItem(entity=record.entity, state=rules_of(record, Dnd5eItemState))


@dataclass
class Dnd5eWorld:
    state: Dnd5eState
    rng: Random
    ruleset: Ruleset

    def actor(self, actor_id: EntityId) -> Dnd5eActor:
        return read_actor(self.state, actor_id)

    def item(self, item_id: EntityId) -> Dnd5eItem:
        return read_item(self.state, item_id)

    def player(self) -> Dnd5eActor:
        return self.actor(PLAYER_ID)

    def progression(self) -> Progression:
        progression = self.player().progression
        if progression is None:
            raise ValueError("the player has no class")
        return progression

    def actor_here(self, entity_id: EntityId) -> Dnd5eActor:
        """Reject off-screen actors because this turn cannot visibly affect them."""
        return self.actor(require_actor_here(self.state, entity_id).id)

    def target(self, entity_id: EntityId | None) -> Dnd5eActor:
        """Default to the player because roles never see the player ID."""
        return self.player() if entity_id is None else self.actor_here(entity_id)

    def carried_by(self, actor_id: EntityId) -> tuple[Dnd5eItem, ...]:
        return tuple(self.item(entity.id) for entity in self.state.world.children(actor_id, "item"))

    def commit(self) -> Dnd5eState:
        return self.state.committed()
