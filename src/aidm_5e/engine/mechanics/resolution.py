from collections.abc import Sequence
from dataclasses import dataclass, replace
from random import Random
from typing import Self

from ...domain.models.base import EntityId
from ...domain.models.entities import ActorEntity, Entity, ItemEntity
from ...domain.models.events import Event
from ...domain.models.progression import Progression
from ...domain.models.state import GameState
from ...domain.reducer import apply
from ..ruleset import Ruleset


@dataclass(frozen=True, slots=True)
class Resolution:
    state: GameState
    rng: Random
    ruleset: Ruleset

    def then(self, events: Sequence[Event]) -> Self:
        return replace(self, state=apply(self.state, events))

    @property
    def player(self) -> ActorEntity:
        return self.state.player

    @property
    def progression(self) -> Progression:
        progression = self.player.progression
        if progression is None:
            raise ValueError("the player has no class")
        return progression

    def entity(self, entity_id: EntityId) -> Entity:
        return self.state.world.require(entity_id)

    def of_kind[T: Entity](self, entity_id: EntityId, expected: type[T]) -> T:
        return self.state.world.require_kind(entity_id, expected)

    def actor_here(self, entity_id: EntityId) -> ActorEntity:
        """Reject off-screen actors because this turn cannot visibly affect them."""
        actor = self.of_kind(entity_id, ActorEntity)
        if actor.location_id != self.player.location_id:
            raise ValueError(f"cannot affect {entity_id!r}: not at the player's location")
        return actor

    def target(self, entity_id: EntityId | None) -> ActorEntity:
        """Default to the player because roles never see the player ID."""
        return self.player if entity_id is None else self.actor_here(entity_id)

    def held(self, entity_id: EntityId, verb: str) -> ItemEntity:
        item = self.of_kind(entity_id, ItemEntity)
        if item.container_id != self.player.id:
            raise ValueError(f"cannot {verb} {entity_id!r}: the player is not carrying it")
        return item
