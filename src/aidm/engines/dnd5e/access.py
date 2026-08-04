from dataclasses import dataclass, field
from random import Random

from aidm.core.base import PLAYER_ID, EntityId
from aidm.core.content import Rules
from aidm.core.tools import require_actor_here
from aidm.core.world import GameState

from .ruleset import Ruleset
from .state import Dnd5eActor, Dnd5eActorState, Dnd5eItem, Dnd5eItemState, Progression


def actor_state(rules: Rules) -> Dnd5eActorState:
    return Dnd5eActorState.model_validate(rules)


def item_state(rules: Rules) -> Dnd5eItemState:
    return Dnd5eItemState.model_validate(rules)


def read_actor(state: GameState, actor_id: EntityId) -> Dnd5eActor:
    """A detached read for reporting and validation; only a `Dnd5eWorld` writes payloads back."""
    record = state.world.record(actor_id, "actor")
    return Dnd5eActor(entity=record.entity, state=actor_state(record.rules))


def read_item(state: GameState, item_id: EntityId) -> Dnd5eItem:
    record = state.world.record(item_id, "item")
    return Dnd5eItem(entity=record.entity, state=item_state(record.rules))


def read_player(state: GameState) -> Dnd5eActor:
    return read_actor(state, PLAYER_ID)


@dataclass
class Dnd5eWorld:
    """One action's view of the draft, with the dice and rules it reads."""

    state: GameState
    rng: Random
    ruleset: Ruleset
    _actors: dict[EntityId, Dnd5eActorState] = field(default_factory=dict, init=False, repr=False)
    _items: dict[EntityId, Dnd5eItemState] = field(default_factory=dict, init=False, repr=False)

    def actor(self, actor_id: EntityId) -> Dnd5eActor:
        record = self.state.world.record(actor_id, "actor")
        payload = self._actors.get(actor_id)
        if payload is None:
            payload = actor_state(record.rules)
            self._actors[actor_id] = payload
        return Dnd5eActor(entity=record.entity, state=payload)

    def item(self, item_id: EntityId) -> Dnd5eItem:
        record = self.state.world.record(item_id, "item")
        payload = self._items.get(item_id)
        if payload is None:
            payload = item_state(record.rules)
            self._items[item_id] = payload
        return Dnd5eItem(entity=record.entity, state=payload)

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

    def flush(self) -> None:
        for entity_id, payload in (*self._actors.items(), *self._items.items()):
            self.state.world.record(entity_id).rules = payload.model_dump(mode="json")

    def commit(self) -> GameState:
        self.flush()
        return self.state.committed()
